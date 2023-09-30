import copy
import itertools
from functools import cache

from django import forms
from django.contrib import messages
from django.contrib.admin import FieldListFilter, helpers
from django.contrib.admin.options import ModelAdmin
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.utils import get_fields_from_path, model_format_dict
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Field
from django.http import Http404
from django.template.loader import get_template
from django.http.response import HttpResponseBase, HttpResponseRedirect
from django.template import engines
from django.utils.translation import gettext_lazy as _
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from .. import settings

IGNORED_PARAMS = ("page",)


def action(
	function=None, *, permissions=None, description=None, allow_select_across=False
):
	"""
	Like the Django @admin.action decorator, except with the ability to specify
	if this action should be allowed for 'select_across' requests or should be
	limited to a discrete queryset instead.
	"""

	def decorator(func):
		if permissions is not None:
			func.allowed_permissions = permissions
		if description is not None:
			func.short_description = description
		func.allow_select_across = allow_select_across
		return func

	if function is None:
		return decorator
	else:
		return decorator(function)


class ActionException(Exception):
	pass


class SelectActionMixin(MultipleObjectMixin):
	model = None
	actions = None
	action_form = helpers.ActionForm
	action_form_template = settings.SELECT_ACTION_TEMPLATE
	action_selection_max = None
	actions_selection_counter = True

	def setup(self, request, *args, **kwargs):
		super().setup(request, *args, **kwargs)
		# copy GET params
		self.params = dict(request.GET.items())

	def post(self, request, *args, **kwargs):
		if "action" in request.POST:
			queryset = self.get_queryset()
			response = self.response_action(request, queryset=queryset)
			if isinstance(response, HttpResponseBase):
				return response
		if hasattr(super(), "post"):
			return super().post(request, *args, **kwargs)

	def _get_base_actions(self):
		actions = (self.get_action(action) for action in self.actions or [])
		# get_action might have returned None, so filter any of those out.
		return [action for action in actions if action]

	def get_actions(self, request):
		"""
		The same as the original implementation, except without
		the 'IS_POPUP_VAR' test.
		"""
		# If self.actions is set to None that means actions are disabled on
		# this page.
		if self.actions is None:
			return {}
		actions = self._filter_actions_by_permissions(request, self._get_base_actions())
		return {name: (func, name, desc) for func, name, desc in actions}

	def get_action_choices(self, request, default_choices=models.BLANK_CHOICE_DASH):
		"""
		The same as the original implementation, except without
		presuming `opts` is a member of `self`.
		"""
		opts = self.model._meta
		choices = [] + default_choices
		for func, name, description in self.get_actions(request).values():
			choice = (name, description % model_format_dict(opts))
			choices.append(choice)
		return choices

	def get_action(self, action):
		"""
		Similar to ModelAdmin.get_action, except isn't reliant on
		having an `admin_site` member.
		"""
		# If the action is a callable, just use it.
		if callable(action):
			func = action
			action = action.__name__

		# Next, look for a method. Grab it off self.__class__ to get an unbound
		# method instead of a bound one; this ensures that the calling
		# conventions are the same for functions and methods.
		elif hasattr(self.__class__, action):
			func = getattr(self.__class__, action)

		else:
			return None

		description = ModelAdmin._get_action_description(func, action)
		return func, action, description

	def get_action_form_class(self):
		return self.action_form

	def get_action_form_kwargs(self):
		return {}

	def get_action_form(self):
		ActionForm = self.get_action_form_class()
		action_form = ActionForm(**self.get_action_form_kwargs())
		action_form.fields["action"].choices = self.get_action_choices(self.request)
		return action_form

	def get_action_form_url(self, request):
		return self.get_query_string()

	def can_select_across(self, request, action):
		return getattr(action, "allow_select_across", False)

	def handle_action_finished(self, request):
		return HttpResponseRedirect(request.get_full_path())

	# borrowed from django.admin.options.ModelAdmin;
	# set selection cap
	def response_action(self, request, queryset):
		"""
		Handle an admin action. This is called if a request is POSTed to the
		changelist; it returns an HttpResponse if the action was handled, and
		None otherwise.
		"""
		# Construct the action form.
		data = request.POST.copy()
		data.pop(helpers.ACTION_CHECKBOX_NAME, None)
		data.pop("index", None)

		action_form = self.action_form(data, auto_id=None)
		action_form.fields["action"].choices = self.get_action_choices(request)

		# If the form's valid we can handle the action.
		if action_form.is_valid():
			action = action_form.cleaned_data["action"]
			select_across = action_form.cleaned_data["select_across"]
			func = self.get_actions(request)[action][0]

			# Get the list of selected PKs. If nothing's selected, we can't
			# perform an action on it, so bail. Except we want to perform
			# the action explicitly on all objects.
			selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
			if not selected and not select_across:
				# Reminder that something needs to be selected or nothing will happen
				msg = _(
					"Items must be selected in order to perform "
					"actions on them. No items have been changed."
				)
				messages.warning(request, msg)
				return None

			if (
				not select_across
				and self.action_selection_max is not None
				and len(selected) > self.action_selection_max
			):
				msg = _(
					"Only a maximum of %(num)i items can be selected at a time."
				) % {"num": self.action_selection_max}
				messages.error(request, msg)
				return None

			# Perform the action
			if not select_across:
				queryset = queryset.filter(pk__in=selected)
			elif not self.can_select_across(request, func):
				msg = _(
					"This action requires a discrete selection of items, not all of them."
				)
				messages.error(request, msg)
				return None

			try:
				response = func(self, request, queryset)
			except ActionException as e:
				messages.error(request, str(e))

			# Actions may return an HttpResponse-like object, which will be
			# used as the response from the POST. If not, we'll be a good
			# little HTTP citizen and redirect back to the changelist page.
			if "response" in locals() and isinstance(response, HttpResponseBase):
				return response
			return self.handle_action_finished(request)
		else:
			msg = _("No action selected.")
			messages.warning(request, msg)
			return None

	def get_selection(self, queryset):
		raise NotImplementedError(
			"You must implement a method to distinguish which items are selected."
		)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		template = get_template(self.action_form_template)
		context["action_form"] = template.render(
			{
				"model": self.model,
				"form": self.get_action_form(),
				"actions_selection_counter": self.actions_selection_counter,
				"selection_list": self.get_selection(
					context["page_obj"] or context["object_list"]
				),
				"result_count": len(context["object_list"]),
				"result_list": context["page_obj"] or context["object_list"],
			}
		)
		context["action_form_url"] = self.get_action_form_url(self.request)
		return context

	get_query_string = ChangeList.get_query_string
	_filter_actions_by_permissions = ModelAdmin._filter_actions_by_permissions


class ListFilterMixin(MultipleObjectMixin):
	model = None
	modeladmin_class = None
	list_filter = None
	list_filter_template = settings.LIST_FILTER_TEMPLATE
	list_filters_template = settings.LIST_FILTERS_TEMPLATE

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# copy list_filter so we don't modify the class variable
		# when/if making dynamic changes within the instance
		self.list_filter = copy.deepcopy(type(self).list_filter)

	def setup(self, request, *args, **kwargs):
		super().setup(request, *args, **kwargs)
		# copy GET params
		self.params = dict(request.GET.items())
		if not hasattr(self, "model_admin"):
			self.model_admin = (
				self.modeladmin_class(self.model, AdminSite())
				if self.modeladmin_class
				else ModelAdmin(self.model, AdminSite())
			)

	def has_active_filters(self):
		filter_params = itertools.chain.from_iterable(
			[filter.expected_parameters() for filter in self.get_filter_specs()]
		)
		return any([param in filter_params for param in self.params])

	# borrowed from django.contrib.admin
	@cache
	def get_filter_specs(self):
		lookup_params = self.get_filters_params()
		filter_specs = []
		for list_filter in self.list_filter:
			if callable(list_filter):
				# This is simply a custom list filter class.
				spec = list_filter(
					self.request, lookup_params, self.model, self.model_admin
				)
			else:
				field_path = None
				if isinstance(list_filter, (tuple, list)):
					# This is a custom FieldListFilter class for a given field.
					field, field_list_filter_class = list_filter
				else:
					# This is simply a field name, so use the default
					# FieldListFilter class that has been registered for the
					# type of the given field.
					field, field_list_filter_class = list_filter, FieldListFilter.create
				if not isinstance(field, Field):
					field_path = field
					field = get_fields_from_path(self.model, field_path)[-1]

				spec = field_list_filter_class(
					field,
					self.request,
					lookup_params,
					self.model,
					self.model_admin,
					field_path=field_path,
				)
			if spec and spec.has_output():
				spec.template = self.list_filter_template
				filter_specs.append(spec)
		return filter_specs

	def clear_all_filters(self):
		filter_params = itertools.chain.from_iterable(
			[filter.expected_parameters() for filter in self.get_filter_specs()]
		)
		return self.get_query_string(remove=filter_params)

	def get_queryset(self):
		queryset = super().get_queryset()
		filters = self.get_filter_specs()
		for filter in filters:
			queryset = filter.queryset(self.request, queryset)
		return queryset

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		template = get_template(self.list_filters_template)
		context['list_filters'] = template.render({'view': self})
		return context

	get_query_string = ChangeList.get_query_string
	get_filters_params = ChangeList.get_filters_params


class AdjustablePaginationMixin(MultipleObjectMixin):
	pagination_choices = [25, 50, 100, 200]
	pagination_field_class = forms.ChoiceField
	pagination_param = "paginate_by"
	pagination_form = forms.Form
	pagination_form_template = settings.ADJUSTABLE_PAGINATION_TEMPLATE

	def setup(self, request, *args, **kwargs):
		super().setup(request, *args, **kwargs)
		# copy GET params
		self.params = dict(request.GET.items())

	def get_paginate_by(self, queryset=None):
		try:
			param = int(self.request.GET.get(self.pagination_param, 0))
		except TypeError:
			param = 0
		choices = []
		for i in self.pagination_choices:
			choices.append((abs(i - param), i))
		choice = sorted(choices, key=lambda x: x[0])[0][1]
		return choice

	def get_pagination_choices(self):
		return sorted(
			[(i, str(i)) for i in self.pagination_choices], key=lambda x: x[0]
		)

	def get_pagination_field_class(self):
		return self.pagination_field_class

	def get_pagination_field_kwargs(self):
		return {}

	def get_pagination_form(self):
		field_class = self.get_pagination_field_class()
		form_class = type(
			f"{type(self).__name__}PaginationForm",
			(self.pagination_form,),
			{
				"template_name": self.pagination_form_template,
				"paginate_by": field_class(
					label=_("Paginate by"),
					choices=self.get_pagination_choices(),
					initial=self.get_paginate_by(),
					required=False,
					**self.get_pagination_field_kwargs(),
				),
			},
		)
		return form_class()

	def get_pagination_form_url(self, request):
		return self.get_query_string(remove=[self.pagination_param])

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["pagination_form"] = self.get_pagination_form()
		context["pagination_form_url"] = self.get_pagination_form_url(self.request)
		return context

	get_query_string = ChangeList.get_query_string


class MultipleLookupMixin(SingleObjectMixin):
	lookup_fields = []
	lookup_url_kwarg = None

	def get_object(self, queryset=None):
		if len(self.lookup_fields) == 0:
			raise AttributeError("'lookup_fields' cannot be empty")
		if not self.lookup_url_kwarg:
			raise AttributeError("'lookup_url_kwarg' must be specified")
		queryset = queryset or self.get_queryset()
		for i, field in enumerate(self.lookup_fields):
			try:
				return queryset.get(**{field: self.kwargs.get(self.lookup_url_kwarg)})
			except (ValueError, ValidationError, queryset.model.DoesNotExist):
				if i == (len(self.lookup_fields) - 1):
					raise Http404(
						_("No %(verbose_name)s found matching the query")
						% {"verbose_name": queryset.model._meta.verbose_name}
					)
