# -*- coding: utf-8 -*-
from django import template
from django.utils.http import urlencode

register = template.Library()


@register.simple_tag
def build_query_string(request, **params):
    """
    Used for building query parameters dynamically. Useful for 
    combining query parameters which may be separate and distinct 
    but need to be remembered, such as htmx swapped content.
    
    Example:
    
    {% with my_value=5 %}
        <a href="{% url 'myurl' %}?{% build_query_string request myParam=my_value anotherParam='true' %}">
            link
        </a>
    {% endwith %}
    """
    params = params or {}
    p = request.GET.copy() if request else {}
    for k, v in params.items():
        if v is None:
            if k in p:
                del p[k]
        else:
            p[k] = v
    return "%s" % urlencode(sorted(p.items()))
