# -*- coding: utf-8 -*-
from django import template
from django.db.models import Model

register = template.Library()


@register.filter
def meta(value):
    """
    Get an object's _meta instance. Helpful to get a model's (or any 
    object with a _meta variable) meta instance dynamically.
    
    Example:
    
    # meta is accessible
    {% with meta=object|meta %}
        {{ meta.verbose_name }}
    {% endwith %}
    
    # throws error
    {{ object._meta.verbose_name }}
    """
    return getattr(value, "_meta")


@register.filter
def field_verbose_name(meta, field_name):
    """
    Retrieves the verbose name for a model field. Useful for pulling 
    internationalized verbose names of fields directly into templates.
    
    Example:
    
    <label>{{ object|field_verbose_name:'name' }}</label>
    """
    if isinstance(meta, Model):
        meta = meta._meta
    return meta.get_field(field_name).verbose_name


@register.filter(name="hasattr")
def hasattr_filter(obj, attr):
    """
    Determines if an object has the specified attribute. Use this to 
    safely access reverse relationships which may not existing from 
    within your template.
    
    Example:
    
    #raises no exception
    {% if user|hasattr:'supervisor_of' %}
        ...
    {% endif %}
    
    # raises exception
    {% if user.supervisor_of %}
        ...
    {% endif %}
    """
    return hasattr(obj, attr)
