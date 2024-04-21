from django import template
from django.template.loader import get_template

register = template.Library()


@register.simple_tag
def list_filter(view, spec):
	tpl = get_template(spec.template)
	return tpl.render({
		"request": view.request,
		"title": spec.title,
		"choices": list(spec.choices(view)),
		"spec": spec,
	})
