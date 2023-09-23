# -*- coding: utf-8 -*-
from django.contrib.auth.mixins import UserPassesTestMixin


class ModelUserFieldPermissionMixin(UserPassesTestMixin):
	model_permission_user_field = 'user'

	def get_model_permission_user_field(self):
		return self.model_permission_user_field

	def test_func(self):
		model_attr = self.get_model_permission_user_field()
		current_user = self.request.user
		if getattr(self, 'object', None):
			object = self.object
		elif hasattr(self, 'get_object'):
			object = self.get_object()
		else:
			self.get_queryset().first()

		return current_user == getattr(object, model_attr)
