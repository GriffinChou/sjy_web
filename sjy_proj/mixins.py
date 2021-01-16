# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
from django.apps import apps
from django.core.cache import cache, utils
from django.http import Http404, HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.utils.encoding import force_text
from django.urls import reverse_lazy

# Create your views here.

#导入自定义方法
from sjy_proj.lib.utils import (
    get_query_string, get_content_type_for_model, has_permission
)

#从app中导入要初始化的内容
from sjy_proj.models import Configure, data_c
system_menus_key = utils.make_template_fragment_key('system.menus')

#构建主页菜单
def construct_menus(user):
    model_names = []
    for app in apps.get_app_config('sjy_proj').get_models():
        opts = app._meta
        if has_permission(opts, user, 'view') and \
                not getattr(opts, 'hidden', False):
            icon_color = 'text-' + opts.icon_color if opts.icon_color else ''
            meta = {
                'model_name': opts.model_name,
                'verbose_name': opts.verbose_name,
                'icon': opts.icon,
                'icon_color': icon_color,
                'level': opts.level,
            }
            model_names.append(meta)
    counts = list(set([i.get('level') for i in model_names]))
    new_menus = []
    for i in counts:
        new_menus.append(
            [c for c in model_names if c.get('level') == i]
        )
    return new_menus


class BaseRequiredMixin(LoginRequiredMixin):

    cmodel = ''

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "系统需要登录才能访问")
            return redirect_to_login(
                request.get_full_path(),
                self.get_login_url(), self.get_redirect_field_name()
            )

        # if not request.user.onidc:
        #     idc = data_c.objects.filter(actived=True)
        #     if idc.count() == 0 and request.user.is_superuser:
        #         messages.info(
        #             request,
        #             "您必须新建一个数据中心才能使用该系统"
        #         )
        #         return HttpResponseRedirect('/welcome/')
        #     return self.handle_no_permission()
        model = self.kwargs.get('model', self.cmodel)
        onidc = request.user.onidc
        self.onidc_id = onidc.id
        self.title = "{} 神经元管理平台".format(onidc.name)
        if model:
            try:
                self.model = apps.get_model('sjy_proj', model.lower())
                self.opts = self.model._meta
                self.model_name = self.opts.model_name
                self.verbose_name = self.opts.verbose_name
                if self.kwargs.get('pk', None):
                    self.pk_url_kwarg = self.kwargs.get('pk')
            except BaseException:
                raise Http404("您访问的模块不存在.")
        return super(BaseRequiredMixin, self).dispatch(
            request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BaseRequiredMixin, self).get_context_data(**kwargs)
        self.meta = {}
        try:
            self.meta['logo'] = self.request.user.onidc.name
            self.meta['icon'] = self.opts.icon
            self.meta['model_name'] = self.model_name
            self.meta['verbose_name'] = self.verbose_name
            self.meta['title'] = "{} {}".format(self.verbose_name, self.title)
        except BaseException:
            self.meta['title'] = self.title
        context['meta'] = self.meta
        context['menus'] = cache.get_or_set(
            system_menus_key + str(self.request.user.id),
            construct_menus(self.request.user), 1800
        )
        return context