# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import functools

from django import forms
from django.db.models import Max
from six import text_type
from django.utils.html import format_html
from django.utils.text import get_text_list
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.forms import UserCreationForm


#主页显示的选项
from sjy_proj.models import (
     Comment, User, Configure,data_c,program

)

from sjy_proj.lib.utils import can_create, shared_queryset

STATICROOT = '/static/sjy_proj/'

MIME_ACCEPT = '''
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,
application/vnd.ms-excel,
'''

class InitIdcForm(forms.ModelForm):
    class Meta:
        model = data_c
        fields = [
            'name',
            'desc',
            'address',
            'tel'
                  ]

    def __init__(self, *args, **kwargs):
        super(InitIdcForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                {'autocomplete': "off", 'class': "form-control"})

#导出表单
class ImportExcelForm(forms.Form):
    excel = forms.FileField(
        label="excel文件",
        help_text="请上传xls或xlsx文件",
        widget=forms.ClearableFileInput(
            attrs={
                'multiple': True,
                # 'class': "form-control",
                'accept': MIME_ACCEPT.strip()
            }
        )
    )


class Select2Media(object):
    class Media:
        css = {
            'all': (
                '/static/sjy_proj/css/select2.min.css',
            )
        }

        js = (
            '/static/sjy_proj/js/select2.min.js',
            '/static/sjy_proj/js/i18n/zh-CN.js',
        )


class CheckUniqueTogether(forms.ModelForm):

    def get_unique_together(self):
        unique_together = self.instance._meta.unique_together
        for field_set in unique_together:
            return field_set
        return None

    def clean(self):
        # self.validate_unique()
        cleaned_data = super(CheckUniqueTogether, self).clean()
        unique_fields = self.get_unique_together()
        if isinstance(unique_fields, (list, tuple)):
            unique_filter = {}
            instance = self.instance
            model_name = instance._meta.verbose_name
            for unique_field in unique_fields:
                field = instance._meta.get_field(unique_field)
                if field.editable and unique_field in self.fields:
                    unique_filter[unique_field] = cleaned_data.get(
                        unique_field)
                else:
                    unique_filter[unique_field] = getattr(
                        instance, unique_field)
            for k, v in unique_filter.items():
                if not v:
                    return
            existing_instances = type(instance).objects.filter(
                **unique_filter).exclude(pk=instance.pk)
            if existing_instances:
                field_labels = [
                    instance._meta.get_field(f).verbose_name
                    for f in unique_fields
                ]
                field_labels = text_type(get_text_list(field_labels, _('and')))
                msg = _("%(model_name)s with this %(field_labels)s already exists.") % {
                    'model_name': model_name, 'field_labels': field_labels, }
                for unique_field in unique_fields:
                    if unique_field in self.fields:
                        self.add_error(unique_field, msg)





class FormBaseMixin(Select2Media, CheckUniqueTogether):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(FormBaseMixin, self).__init__(*args, **kwargs)
        if 'mark' in self.fields:
            self.fields['mark'].widget = forms.HiddenInput()
        if self.user is not None:
            onidc_id = self.user.onidc_id
            effective = {
                'onidc_id': onidc_id,
                'deleted': False,
                'actived': True
            }
            for field_name in self.fields:
                field = self.fields.get(field_name)
                if isinstance(
                        field,
                        (forms.fields.SlugField,
                         forms.fields.CharField)):
                    self.fields[field_name].widget.attrs.update(
                        {'autocomplete': "off"})
                if isinstance(field, forms.fields.DateTimeField):
                    self.fields[field_name].widget.attrs.update(
                        {'data-datetime': "true"})
                if isinstance(field.widget, forms.widgets.Textarea):
                    self.fields[field_name].widget.attrs.update({'rows': "3"})
                if isinstance(field, (
                        forms.models.ModelChoiceField,
                        forms.models.ModelMultipleChoiceField)):
                    fl = ''
                    if getattr(field.queryset.model, 'mark', False):
                        field.queryset = shared_queryset(
                            field.queryset, onidc_id)
                        if field.queryset.model is program:
                            _prefix = self._meta.model._meta.model_name
                            _postfix = field_name.capitalize()
                            flag = _prefix.capitalize() + '-' + _postfix
                            fl = flag
                            field_initial = field.queryset.filter(
                                master=True, flag=flag)
                            if field_initial.exists():
                                field.initial = field_initial.first()
                    else:
                        field.queryset = field.queryset.filter(**effective)
                    mn = field.queryset.model._meta
                    if can_create(mn, self.user) and fl:
                        fk_url = format_html(
                            ''' <a title="点击添加一个 {}"'''
                            ''' href="/new/{}/?flag={}">'''
                            '''<i class="fa fa-plus"></i></a>'''.format(
                                field.label, mn.model_name, fl))
                    elif can_create(mn, self.user) and not fl:
                        fk_url = format_html(
                            ''' <a title="点击添加一个 {}"'''
                            ''' href="/new/{}">'''
                            '''<i class="fa fa-plus"></i></a>'''.format(
                                field.label, mn.model_name))
                    else:
                        fk_url = ''
                    field.help_text = field.help_text + fk_url
                self.fields[field_name].widget.attrs.update(
                    {'class': "form-control"})



#添加备注信息表单
class DetailNewCommentForm(FormBaseMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']