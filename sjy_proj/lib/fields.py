# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.db.models.fields import CharField, Field
from django import forms
from django.core.exceptions import ValidationError


MAX_NETWORK_ADDRESS_LENGTH = 44


class NullableFormFieldMixin(object):
    def to_python(self, value):
        """Returns a Unicode object."""
        if value in self.empty_values:
            return None
        return super(NullableFormFieldMixin, self).to_python(value)


class NullableCharFormField(NullableFormFieldMixin, forms.CharField):
    pass



class NullableCharFieldMixin(object):
    """
    Mixin for char fields and descendants which will replace empty string value
    ('') by null when saving to the database.
    It's especially useful when field is marked as unique and at the same time
    allows null/blank (`models.CharField(unique=True, null=True, blank=True)`)
    """
    _formfield_class = NullableCharFormField

    def get_prep_value(self, value):
        r = super(NullableCharFieldMixin, self).get_prep_value(value) or None
        return r

    def formfield(self, **kwargs):
        defaults = {}
        if self._formfield_class:
            defaults['form_class'] = self._formfield_class
        defaults.update(kwargs)
        return super(NullableCharFieldMixin, self).formfield(**defaults)


class NullableCharField(NullableCharFieldMixin, models.CharField):
    pass