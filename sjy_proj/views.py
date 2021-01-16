# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
import json
import time


from django.apps import apps
from django.shortcuts import render
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.views.generic import View, TemplateView
from django.views.generic.edit import FormView
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetView,
    PasswordResetDoneView, PasswordResetConfirmView,
    PasswordResetCompleteView, PasswordChangeDoneView,
    PasswordChangeView
)
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.urls import reverse_lazy


# Create your views here.
from sjy_proj.mixins import BaseRequiredMixin
#导入模型中创建的table模块
from sjy_proj.models import (
    program,  ContentType,  Attachment
)

#导入自定义工具类模块
from sjy_proj.lib.utils import shared_queryset, get_content_type_for_model



#登录前的处理
login = LoginView.as_view(template_name='accounts/login.html')

logout = LogoutView.as_view(template_name='accounts/logout.html')

password_reset = PasswordResetView.as_view(
    template_name='accounts/password_reset_form.html',
    email_template_name='accounts/password_reset_email.html',
    subject_template_name='accounts/password_reset_subject.txt',
)

password_reset_done = PasswordResetDoneView.as_view(
    template_name='accounts/password_reset_done.html'
)

reset = PasswordResetConfirmView.as_view(
    template_name='accounts/password_reset_confirm.html'
)

reset_done = PasswordResetCompleteView.as_view(
    template_name='accounts/password_reset_complete.html'
)


class PasswordChangeView(BaseRequiredMixin, PasswordChangeView):
    template_name = 'accounts/password_change_form.html'
    success_url = reverse_lazy('idcops:index')


password_change = PasswordChangeView.as_view()

password_change_done = PasswordChangeDoneView.as_view(
    template_name='accounts/password_change_done.html'
)