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
     Comment, User, Configure,data_c

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
