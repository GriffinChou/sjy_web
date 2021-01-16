# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import uuid
import json
import socket
import struct
import ipaddress
from django.db import models, transaction
from django.db.models.fields import BLANK_CHOICE_DASH
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import (
    GenericForeignKey, GenericRelation
)

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import formats, timezone
from django.utils.encoding import  force_text
from six import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import logger
from django.urls import reverse_lazy



#上传文件
def upload_to(instance, filename):
    ext = filename.split('.')[-1]
    filename = "%s.%s" % (uuid.uuid4(), ext)
    today = timezone.datetime.now().strftime(r'%Y/%m/%d')
    return os.path.join('uploads', today, filename)


EXT_NAMES = (
    'level', 'hidden', 'dashboard', 'metric', 'icon',
    'icon_color', 'default_filters', 'list_display', 'extra_fields'
)

models.options.DEFAULT_NAMES += EXT_NAMES
#标记状态
COLOR_MAPS = (
    ("red", "红色"),
    ("orange", "橙色"),
    ("yellow", "黄色"),
    ("green", "深绿色"),
    ("blue", "蓝色"),
    ("muted", "灰色"),
    ("black", "黑色"),
    ("aqua", "浅绿色"),
    ("gray", "浅灰色"),
    ("navy", "海军蓝"),
    ("teal", "水鸭色"),
    ("olive", "橄榄绿"),
    ("lime", "高亮绿"),
    ("fuchsia", "紫红色"),
    ("purple", "紫色"),
    ("maroon", "褐红色"),
    ("white", "白色"),
    ("light-blue", "暗蓝色"),
)

#项目状态
state = (('0','未开始'),
         ('1','照片元数据提取'),
         ('2','pos处理'),
         ('3','pos写入'),
         ('4','已完成'),)

#其他标记
class Mark(models.Model):
    CHOICES = (
        ('shared', "已共享的"),
        ('pre_share', "预共享的"),
    )
    mark = models.CharField(
        max_length=64, choices=CHOICES,
        blank=True, null=True,
        verbose_name="系统标记", help_text="系统Slug内容标记")

    class Meta:
        level = 0
        hidden = False
        dashboard = False
        metric = ""
        icon = 'fa fa-circle-o'
        icon_color = ''
        default_filters = {'deleted': False}
        list_display = '__all__'
        extra_fields = []
        abstract = True

    @cached_property
    def get_absolute_url(self):
        opts = self._meta
        # if opts.proxy:
        #    opts = opts.concrete_model._meta
        url = reverse_lazy('sjy_proj:detail', args=[opts.model_name, self.pk])
        return url

    @cached_property
    def get_edit_url(self):
        opts = self._meta
        url = reverse_lazy('sjy_proj:update', args=[opts.model_name, self.pk])
        return url

    def title_description(self):
        return self.__str__()


'''
3.创建项目表，包含项目名称、客户名称、项目状态、创建人、项目描述和创建时间等
option -------program
'''
@python_2_unicode_compatible
class program():
    p_name = models.CharField(
        max_length=64,
        verbose_name="项目名称",
        help_text="自定义该项目的名称")

    flag = models.SlugField(
        max_length=64,
        choices=BLANK_CHOICE_DASH,
        verbose_name="标记类型",
        help_text="创建项目，请选择“所属项目”")

    description = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="项目描述",
        help_text="可以填写项目背景等内容")

    color = models.SlugField(
        max_length=12,
        choices=COLOR_MAPS,
        null=True, blank=True,
        verbose_name="状态",
        help_text="状态标签，用于显示当前项目进行到哪一步")

    def __init__(self, *args, **kwargs):
        super(program, self).__init__(*args, **kwargs)
        flag = self._meta.get_field('flag')
        flag.choices = self.choices_to_field()

    @classmethod
    def choices_to_field(cls):
        _choices = [BLANK_CHOICE_DASH[0], ]
        for rel in cls._meta.related_objects:
            object_name = rel.related_model._meta.object_name.capitalize()
            field_name = rel.remote_field.name.capitalize()
            name = "{}-{}".format(object_name, field_name)
            remote_model_name = rel.related_model._meta.verbose_name
            verbose_name = "{}-{}".format(
                remote_model_name, rel.remote_field.verbose_name
            )
            _choices.append((name, verbose_name))
        return sorted(_choices)

    @property
    def flag_to_dict(self):
        maps = {}
        for item in self.choices_to_field():
            maps[item[0]] = item[1]
        return maps

    def clean_fields(self, exclude=None):
        super(program, self).clean_fields(exclude=exclude)
        if not self.pk:
            verify = self._meta.model.objects.filter(
                onidc=self.onidc, master=self.master, flag=self.flag)
            if self.master and verify.exists():
                raise ValidationError({
                    'text': "标记类型: {} ,机房已经存在一个默认使用的标签: {}"
                            " ({}).".format(self.flag_to_dict.get(self.flag),
                                            self.text, self.description)})

    def __str__(self):
        return self.text

    def title_description(self):
        text = '{} > {}'.format(self.get_flag_display(), self.text)
        return text

    def save(self, *args, **kwargs):
        shared_flag = ['clientkf', 'clientsales', 'goodsbrand', 'goodsunit']
        if self.flag in shared_flag:
            self.mark = 'shared'
        return super(program, self).save(*args, **kwargs)

    class Meta(Mark.Meta):
        level = 2
        icon = 'fa fa-cogs'
        metric = "项"
        list_display = [
            'text', 'flag', 'description', 'master',
            'color',
            'actived', 'onidc', 'mark'
        ]
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        ordering = ['-actived', '-modified']
        unique_together = (('flag', 'text'),)
        verbose_name = verbose_name_plural = "项目管理"

#标记
class Remark(models.Model):
    comment = GenericRelation(
        'Comment',
        related_name="%(app_label)s_%(class)s_comment",
        verbose_name="备注信息")

    @property
    def remarks(self):
        return self.comment.filter(deleted=False, actived=True)

    class Meta:
        abstract = True

#创建人
class Creator(models.Model):
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_creator",
        verbose_name="创建人", help_text="该对象的创建人")

    class Meta:
        abstract = True

#操作
class Operator(models.Model):
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_operator",
        blank=True, null=True,
        verbose_name="修改人", help_text="该对象的修改人"
    )

    class Meta:
        abstract = True

#创建日期
class Created(models.Model):
    created = models.DateTimeField(
        default=timezone.datetime.now, editable=True,
        verbose_name="创建日期", help_text="该对象的创建日期"
    )

    class Meta:
        abstract = True

#修改日期
class Modified(models.Model):
    modified = models.DateTimeField(
        auto_now=True, verbose_name="修改日期",
        help_text="该对象的修改日期"
    )

    class Meta:
        abstract = True
        ordering = ['-modified']

#
class Actived(models.Model):
    actived = models.BooleanField(
        default=True, verbose_name="已启用",
        help_text="该对象是否为有效资源"
    )

    class Meta:
        abstract = True

#删除
class Deleted(models.Model):
    deleted = models.BooleanField(
        default=False,
        verbose_name="已删除", help_text="该对象是否已被删除"
    )

    class Meta:
        abstract = True



class PersonTime(Creator, Created, Operator, Modified):
    class Meta:
        abstract = True


class ActiveDelete(Actived, Deleted):
    class Meta:
        abstract = True

class Contentable(Mark, PersonTime, ActiveDelete):
    content_type = models.ForeignKey(
        ContentType,
        models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('content type'),
        related_name="%(app_label)s_%(class)s_content_type",
        limit_choices_to={'app_label': 'idcops'}
    )
    object_id = models.PositiveIntegerField(
        _('object id'), blank=True, null=True)
    object_repr = GenericForeignKey('content_type', 'object_id')
    content = models.TextField(verbose_name="详细内容", blank=True)

    def __str__(self):
        return force_text(self.object_repr)

    class Meta:
        abstract = True
class Comment(Contentable):
    class Meta(Mark.Meta):
        level = 1
        hidden = getattr(settings, 'HIDDEN_COMMENT_NAVBAR', True)
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        verbose_name = verbose_name_plural = "备注信息"



"""
2.创建用户表，包含用户名、密码、性别、邮箱、电话、创建时间、用户角色、用户头像等字段，
其中用户名、邮箱、电话唯一
"""
class User(AbstractUser,Remark,Mark):
    gender = (
        ('male', "男"),
        ('femal', "女")
    )
    role = (
        ('sjy',"内部员工"),
        ('other',"非内部员工")
    )
    password = models.CharField(max_length=256,verbose_name='密码')
    sex = models.CharField(max_length=128,choices=gender,default="男",verbose_name='性别')
    email = models.EmailField(unique=True,verbose_name='邮箱')
    # phone = models.CharField(max_length=128,verbose_name='电话')

    # user_role = models.CharField(max_length=128,choices=role,default="非内部员工")
    user_image = models.ImageField(max_length=256,default='../static/imgs/sjy.jpg',verbose_name='头像')#默认头像

    #设置外键关系，外键写在多数的一方，用户和角色：多对一
    # role = models.ForeignKey(role,on_delete=models.CASCADE)#设置级联删除



#人性化显示对象信息
    # def __str__(self):
    #     return self.Meta

#用户按创建时间反序排列
    class Meta:
        # ordering = ["-c_time"]
        verbose_name = "用户"
        verbose_name_plural = "用户"



'''
4.创建工程表，包含工程名称、创建时间和状态等字段，
其中关联项目id、照片元数据id、记录id等
'''
class task(models.Model):
    static = (
        ('proceing',"进行中"),
        ('finish',"已完成")
    )
    t_name = models.CharField(max_length=128,)
    c_time = models.DateTimeField(auto_now_add=True)
    t_state = models.CharField(max_length=128,choices=static,default="已完成")

    # 设置外键关系，外键写在多数的一方，工程和项目的关系：多对一
    # project = models.ForeignKey(project,
    #                             on_delete=models.CASCADE,
    #
    #                             )

    # 人性化显示对象信息
    def __str__(self):
        return self.t_name

    # 用户按创建时间反序排列
    class Meta:
        ordering = ["-c_time"]
        verbose_name = "工程名称"
        verbose_name_plural = "工程名称"




"""
5.创建照片元数据表，包含路径和照片对象
关联工程id
"""
class pic_details(models.Model):
    pic_path = models.CharField(max_length=256)
    pic = models.ImageField()



    # 人性化显示对象信息
    def __str__(self):
        return self.pic

    # 按创建时间反序排列
    class Meta:
        verbose_name = "照片元数据"
        verbose_name_plural = "照片元数据"



'''
6.创建POS元数据表，包含路径和列表对象，
关联工程id
'''
class pos(models.Model):
    pos_path = models.CharField(max_length=256)
    pos = models.CharField(max_length=256)

    def __str__(self):
        return self.pos_path

    class Meta:
        verbose_name = "pos元数据"
        verbose_name_plural = "pos元数据"



'''
7.创建统计表，包含文件数量、文件夹数量、需求容量、pos范围以及pos文件中的pos行数、列数、范围等字段，
关联工程id
'''
class count_t(models.Model):
    dic_num = models.CharField(max_length=128)          #文件夹数量
    file_num = models.CharField(max_length=128)         #文件数量
    memory_size = models.CharField(max_length=256)      #某个文件夹中总文件的内存大小
    pic_pos_size = models.CharField(max_length=256)     #文件夹中的POS范围
    pos_lines = models.CharField(max_length=128)         #POS文件中的行数
    pos_raws = models.CharField(max_length=128)         #POS文件中的列数
    pos_range = models.CharField(max_length=128)        #POS文件中的POS范围

    # def __str__(self):
    #     return self.

    class Meta:
        verbose_name = "数据统计"
        verbose_name_plural = "数据统计"



'''
8.异常值记录表，包含异常值类型、异常值名称、异常值数值、路径等，
关联工程id
'''

class abmormal_datas(models.Model):
    am_type = models.CharField(max_length=128)          #异常值类型
    am_name = models.CharField(max_length=128)          #异常值名字
    am_value = models.CharField(max_length=128)         #异常值数值
    am_path = models.CharField(max_length=128)          #异常值路径

    def __str__(self):
        return self.am_name

    class Meta:
        verbose_name = "异常值记录"
        verbose_name_plural = "异常值记录"
















#上传的文件附件Attachment
@python_2_unicode_compatible
class Attachment():
    name = models.CharField(
        max_length=255,
        verbose_name=_("file name")
    )
    file = models.FileField(
        upload_to=upload_to,
        verbose_name=_("file")
    )

    def __str__(self):
        return self.name

    class Meta(Mark.Meta):
        level = 1
        icon = 'fa fa-file'
        metric = "份"
        hidden = True
        list_display = [
            'name',
            'file',
            'created',
            'creator',
            'onidc',
            'tags']
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        verbose_name = verbose_name_plural = "媒体文件"



#
class Contentable():
    content_type = models.ForeignKey(
        ContentType,
        models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('content type'),
        related_name="%(app_label)s_%(class)s_content_type",
        limit_choices_to={'app_label': 'sjy_proj'}
    )
    object_id = models.PositiveIntegerField(
        _('object id'), blank=True, null=True)
    object_repr = GenericForeignKey('content_type', 'object_id')
    content = models.TextField(verbose_name="详细内容", blank=True)

    def __str__(self):
        return force_text(self.object_repr)

    class Meta:
        abstract = True


#
class Configure(Contentable):
    class Meta(Mark.Meta):
        level = 2
        hidden = getattr(settings, 'HIDDEN_CONFIGURE_NAVBAR', True)
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        verbose_name = verbose_name_plural = "用户配置"

    def __str__(self):
        return "{}-{} : {}".format(self.creator, self.content_type, self.pk)


#初始化数据中心
@python_2_unicode_compatible
class data_c(Mark, ):
    name = models.CharField(
        max_length=16,
        unique=True,
        verbose_name="数据中心名称",
        help_text="数据中心名称命名 如：神经元大数据处理"
    )
    #数据中心的描述
    desc = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="描述",
        help_text="对该数据中心的描述"
    )
    address = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="数据中心地址",
        help_text="具体地址如：云南省昆明市五华区"
    )

    tel = models.CharField(
        max_length=32,
        verbose_name="联系方式",
        help_text="联系方式，例如：021-358795"
    )
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        verbose_name="管理人员",
        help_text="权限将比普通用户多一些"
    )

    def __str__(self):
        return self.name

    class Meta(Mark.Meta):
        level = 4
        list_display = [
            'name', 'desc',
            'address', 'tel'
        ]
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        verbose_name = verbose_name_plural = "数据中心"


#部门管理模块 Rack----deparment
class deparment(Mark, PersonTime, ActiveDelete, Remark):
    name = models.CharField(
        max_length=32,
        verbose_name="部门名称",
        help_text="如：财务部"
    )

    unitc = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(180)],
        verbose_name="部门人数",
        help_text="填写部门的人数,默认:20")


    def __str__(self):
        return self.name

    def title_description(self):
        text = '{} > {}'.format(self.zone, self.name)
        return text


    @property
    def units(self):
        qset = self.idcops_unit_rack.all().order_by('-name')
        return qset

    class Meta(Mark.Meta):
        level = 0
        icon = 'fa fa-cube'
        icon_color = 'aqua'
        metric = "个"
        dashboard = True
        default_filters = {'deleted': False, 'actived': True}
        list_display = [
            'name', 'unitc',  'tags',
        ]

        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        ordering = ['-actived', '-modified']
        verbose_name = verbose_name_plural = "部门管理"

#
class Onidc(models.Model):
    onidc = models.ForeignKey(
        'data_c',
        blank=True, null=True, on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_onidc",
        verbose_name="所属项目", help_text="该数据所属的项目"
    )


#日志
class Syslog(Contentable):
    action_flag = models.CharField(_('action flag'), max_length=32)
    message = models.TextField(_('change message'), blank=True)
    object_desc = models.CharField(
        max_length=128,
        verbose_name="对象描述"
    )
    related_client = models.CharField(
        max_length=128,
        blank=True, null=True,
        verbose_name="关系客户"
    )

    def title_description(self):
        time = formats.localize(timezone.template_localtime(self.created))
        text = '{} > {} > {}了 > {}'.format(
            time, self.creator, self.action_flag, self.content_type
        )
        return text

    class Meta(Mark.Meta):
        icon = 'fa fa-history'
        list_display = [
            'created', 'creator', 'action_flag', 'content_type',
            'object_desc', 'related_client', 'message', 'actived',
        ]
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        ordering = ['-created', ]
        verbose_name = verbose_name_plural = _('log entries')



'''
6.创建POS元数据表，包含路径和列表对象，
关联工程id
'''
#pos处理device------>pos
@python_2_unicode_compatible
class POS(Onidc, Mark, PersonTime, ActiveDelete, Remark):
    name = models.SlugField(
        max_length=32,
        unique=True,
        verbose_name="编号",
        help_text="默认最新一个可用编号")
    rack = models.ForeignKey(
        'Rack',
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_rack",
        verbose_name="所属项目",
        help_text="该pos所属的项目信息")
    units = models.ManyToManyField(
        'Unit',
        blank=True,
        verbose_name="设备U位",
        help_text="设备所在机柜中的U位信息")
    client = models.ForeignKey(
        'Client',
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_client",
        verbose_name="所属工程",
        help_text="该pos所属的工程信息")
    # ipaddr = models.Field(
    ipaddr = models.FileField(
        max_length=128,
        blank=False,
        verbose_name="pos地址",
        help_text="比如: C:/datasets/超图pos.txt")
    # model = models.CharField(
    model = models.FileField(
        max_length=128,
        verbose_name="照片地址", help_text="比如: C:/超图/A/")
    style = models.ForeignKey(
        'Option',
        on_delete=models.PROTECT,
        limit_choices_to={'flag': 'Device-Style'},
        related_name="%(app_label)s_%(class)s_style",
        verbose_name="设备类型", help_text="设备类型默认为服务器")

    tags = models.ManyToManyField(
        'Option',
        blank=True, limit_choices_to={'flag': 'Device-Tags'},
        related_name="%(app_label)s_%(class)s_tags",
        verbose_name="设备标签",
        help_text="可拥有多个标签,字段数据来自机房选项"
    )

    def __str__(self):
        return self.name

    def title_description(self):
        text = '{} > {} > {}'.format(
            self.client, self.get_status_display(), self.style
        )
        return text

    def list_units(self):
        value = [force_text(i) for i in self.units.all().order_by('name')]
        if len(value) > 1:
            value = [value[0], value[-1]]
        units = "-".join(value)
        return units

    @property
    def move_history(self):
        ct = ContentType.objects.get_for_model(self, for_concrete_model=True)
        logs = Syslog.objects.filter(
            content_type=ct, object_id=self.pk,
            actived=True, deleted=False, action_flag="修改",
        ).filter(content__contains='"units"')
        history = []
        for log in logs:
            data = json.loads(log.content)
            lus = data.get('units')[0]
            try:
                swap = {}
                swap['id'] = log.pk
                swap['created'] = log.created
                swap['creator'] = log.creator
                ous = Unit.objects.filter(pk__in=lus)
                value = [force_text(i) for i in ous]
                if len(value) > 1:
                    value = [value[0], value[-1]]
                swap['units'] = "-".join(value)
                swap['rack'] = ous.first().rack
                move_type = "跨机柜迁移" if 'rack' in data else "本机柜迁移"
                swap['type'] = move_type
                history.append(swap)
            except Exception as e:
                logger.warning(
                    'rebuliding device history warning: {}'.format(e))
        return history

    def last_rack(self):
        try:
            return self.move_history[0].get('rack')
        except Exception as e:
            logger.warning('Get device last rack warning: {}'.format(e))

    def save(self, *args, **kwargs):
        if not self.pk and not self.sn:
            cls = ContentType.objects.get_for_model(self)
            cls_id = "%02d" % (cls.id)
            try:
                object_id = \
                    cls.model_class().objects.order_by('pk').last().pk + 1
            except Exception:
                object_id = 1
            object_id = "%02d" % (object_id)
            self.sn = str(
                timezone.datetime.now().strftime('%Y%m%d') + cls_id + object_id
            )
        return super(pos, self).save(*args, **kwargs)

    class Meta(Mark.Meta):
        level = 3
        icon = 'fa fa-server'
        metric = "台"
        list_display = [
            'name', 'rack', 'urange', 'client', 'model', 'style',
            'sn', 'ipaddr', 'status', 'actived', 'modified'
        ]
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        ordering = ['-modified']
        unique_together = (('onidc', 'name',),)
        verbose_name = verbose_name_plural = "模型生产"


@python_2_unicode_compatible
class Unit(
    Onidc, Mark, PersonTime, ActiveDelete,
):
    name = models.SlugField(
        max_length=3, verbose_name="姓名",
        help_text="必须是数字字符串,例如：01, 46, 47"
    )

    def __str__(self):
        return self.name

    @property
    def online(self):
        online = self.device_set.filter(actived=True, deleted=False)
        if online.exists():
            return online.first()
        else:
            return False

    def save(self, *args, **kwargs):
        if not self.pk:
            try:
                self.name = "%02d" % (int(self.name))
            except Exception:
                raise ValidationError("必须是数字字符串,例如：01, 46, 47")
        else:
            if not self.online and not self.actived:
                return
            if self.online and self.actived:
                return
        return super(Unit, self).save(*args, **kwargs)

    def clean(self):
        if not self.pk:
            try:
                int(self.name)
            except Exception:
                raise ValidationError("必须是数字字符串,例如：01, 46, 47")
        else:
            if not self.online and not self.actived:
                raise ValidationError('该U位没有在线设备, 状态不能为`True`')
            if self.online and self.actived:
                raise ValidationError('该U位已有在线设备，状态不能为`False`')

    @property
    def repeat(self):
        name = self.name
        last_name = "%02d" % (int(name) + 1)
        try:
            last = Unit.objects.get(rack=self.rack, name=last_name)
        except Exception:
            last = None
        if last:
            if (last.actived == self.actived) and (last.online == self.online):
                return True
        else:
            return False

    class Meta(Mark.Meta):
        level = 0
        icon = 'fa fa-magnet'
        metric = "个"
        list_display = [
            'name',
            'rack',
            'client',
            'actived',
            'modified',
            'operator']
        default_permissions = ('view', 'add', 'change', 'delete', 'exports')
        unique_together = (('rack', 'name'),)
        verbose_name = verbose_name_plural = "通讯录"

