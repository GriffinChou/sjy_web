# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.apps import AppConfig

class SjyProjConfig(AppConfig):
    name = 'sjy_proj'
    verbose_name = "神经元管理平台"

    def ready(self):
        from sjy_proj.lib import signals
