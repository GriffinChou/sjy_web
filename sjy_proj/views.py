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
    data_c, Syslog, POS, deparment,up_pos,
    program,  ContentType,  Attachment
)

#导入自定义工具类模块
from sjy_proj.lib.utils import shared_queryset, get_content_type_for_model


#导入表单模块
from sjy_proj.forms import (
    ImportExcelForm, InitIdcForm,
)


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
    success_url = reverse_lazy('sjy_proj:index')


password_change = PasswordChangeView.as_view()

password_change_done = PasswordChangeDoneView.as_view(
    template_name='accounts/password_change_done.html'
)


@login_required(login_url='/accounts/login/')
def welcome(request):
    datac = data_c.objects.filter(actived=True)
    index_url = reverse_lazy('sjy_proj:index')
    #idc------>datac
    if datac.exists() and not settings.DEBUG:
        messages.warning(
            request, "Initialized, 已经初始化，不需要重新初始化。"
        )
        return HttpResponseRedirect(index_url)
    if request.method == 'POST':
        form = InitIdcForm(request.POST)
        if form.is_valid():
            form.instance.creator = request.user
            form.save()
            request.user.onidc = form.instance
            request.user.save()
            try:
                from django.core.management import call_command
                call_command('loaddata', 'initial_options.json')
            except Exception as e:
                messages.error(
                    request,
                    "loaddata initial_options.json 执行失败...,{}".format(e)
                )
            messages.success(
                request, "初始化完成，请开始使用吧..."
            )
        return HttpResponseRedirect(index_url)
    else:
        form = InitIdcForm()
    return render(request, 'welcome.html', {'form': form})


@login_required(login_url='/accounts/login/')
def switch_onidc(request):
    idcs = request.user.slaveidc.all()
    index_url = reverse_lazy('sjy_proj:index')
    if request.method == 'POST':
        if getattr(settings, 'TEST_ENV', False):
            messages.warning(request, "演示环境，不允许切换机柜")
            return HttpResponseRedirect(index_url)
        new_idc = request.POST.get('new_idc')
        request.user.onidc_id = new_idc
        request.user.save()
        messages.success(request, "您已切换到 {}".format(request.user.onidc.name))
        return HttpResponseRedirect(index_url)
    return render(request, 'user/switch.html', {'idcs': idcs})


#主页视图
class IndexView(BaseRequiredMixin, TemplateView):

    template_name = 'index.html'

    def make_years(self, queryset):
        years = queryset.datetimes('created', 'month')
        # print(years)
        if years.count() > 12:
            ranges = years[(years.count()-12):years.count()]
        else:
            ranges = years[:12]
        return ranges

    def make_device_dynamic_change(self):
        content_type = ContentType.objects.get_for_model(POS)
        logs = Syslog.objects.filter(
            onidc_id=self.onidc_id, content_type=content_type)
        data = {}
        data['categories'] = [m.strftime("%Y-%m")
                              for m in self.make_years(logs)]
        data['moveup'] = []
        data['moving'] = []
        data['movedown'] = []
        for y in self.make_years(logs):
            nlogs = logs.filter(created__year=y.year, created__month=y.month)
            moving = nlogs.filter(
                message__contains='"units"', action_flag="修改").exclude(
                content__contains='"units": [[]').count()
            data['moving'].append(moving)
            moveup = nlogs.filter(action_flag="新增").count()
            data['moveup'].append(moveup)
            cancel_movedown = nlogs.filter(action_flag="取消下架").count()
            movedown = nlogs.filter(action_flag="下架").count()
            data['movedown'].append(movedown-cancel_movedown)
        return data

    def make_rack_dynamic_change(self):
        content_type = ContentType.objects.get_for_model(deparment)
        logs = Syslog.objects.filter(
            onidc_id=self.onidc_id, content_type=content_type)
        data = {}
        data['categories'] = [m.strftime("%Y-%m")
                              for m in self.make_years(logs)]
        data['renew'] = []
        data['release'] = []
        for y in self.make_years(logs):
            nlogs = logs.filter(created__year=y.year, created__month=y.month)
            data['renew'].append(nlogs.filter(action_flag="分配机柜").count())
            data['release'].append(nlogs.filter(action_flag="释放机柜").count())
        return data

    def make_rack_statistics(self):
        data = []
        robjects = deparment.objects.filter(onidc_id=self.onidc_id, actived=True)
        keys = program.objects.filter(
            flag__in=['Rack-Style', 'Rack-Status'],
            actived=True)
        keys = shared_queryset(keys, self.onidc_id)
        for k in keys:
            d = []
            query = {
                k.flag.split('-')[1].lower(): k
            }
            c = robjects.filter(**query).count()
            if c > 0:
                d.append(force_text(k))
                d.append(c)
            if d:
                data.append(d)
        return data

    def make_online_statistics(self):
        data = []
        dobjects = up_pos.objects.filter(onidc_id=self.onidc_id)
        keys = program.objects.filter(flag__in=['Device-Style', 'Device-Tags'])
        keys = shared_queryset(keys, self.onidc_id)
        for k in keys:
            d = []
            if k.flag == 'Device-Style':
                c = dobjects.filter(style=k).count()
            else:
                c = dobjects.filter(tags__in=[k]).count()
            if c > 0:
                d.append(force_text(k))
                d.append(c)
            if d:
                data.append(d)
        return data

    def make_state_items(self):
        state_items = [
            {
                'model_name': app._meta.model_name,
                'verbose_name': app._meta.verbose_name,
                'icon': app._meta.icon,
                'icon_color': 'bg-' + app._meta.icon_color,
                'level': app._meta.level,
                'metric': app._meta.metric,
                'count': app.objects.filter(
                    onidc=self.request.user.onidc).filter(
                    **app._meta.default_filters).count(),
            } for app in apps.get_app_config('idcops').get_models() if getattr(
                app._meta,
                'dashboard')]
        return state_items

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['state_items'] = self.make_state_items()
        context['online_statistics'] = self.make_online_statistics()
        context['device_dynamic_change'] = self.make_device_dynamic_change()
        context['rack_statistics'] = self.make_rack_statistics()
        context['rack_dynamic_change'] = self.make_rack_dynamic_change()
        return context


class ProfileView(BaseRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

