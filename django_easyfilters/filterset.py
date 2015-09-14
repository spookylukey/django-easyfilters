import six

from django import template
from django.template.loader import get_template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.text import capfirst

from .filters import (FILTER_DISPLAY, FILTER_REMOVE,
                      ChoicesFilter, DateTimeFilter,
                      ForeignKeyFilter, ManyToManyFilter,
                      NumericRangeFilter, ValuesFilter)
from .utils import python_2_unicode_compatible


def non_breaking_spaces(val):
    # This helps a lot with presentation, by stopping the links+count from being
    # split over a line end.
    val = val.replace(u'-', u'\u2011')
    return mark_safe(u'&nbsp;'.join(escape(part) for part in val.split(u' ')))


class cachedproperty(object):
    """
    Decorator that creates converts a method with a single
    self argument into a property cached on the instance.
    """
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, type):
        res = instance.__dict__[self.func.__name__] = self.func(instance)
        return res


@python_2_unicode_compatible
class FilterSet(object):

    # If the attribute "template" is provided (as a string), that will be
    # preferred;  otherwise we use the specified template_file
    template = None
    template_file = "django-easyfilters/default.html"

    title_fields = None

    def __init__(self, queryset, params):
        self.params = params
        self.model = queryset.model
        self.filters = self.setup_filters()
        self.qs = self.apply_filters(queryset)

    @cachedproperty
    def title(self):
        return self.make_title()

    def __nonzero__(self):
        return any(self.get_filter_choices(f.field) for f in self.filters)

    def get_filter_choices(self, filter_field):
        if not hasattr(self, '_cached_filter_choices'):
            self._cached_filter_choices = dict((f.field, f.get_choices(self.qs))
                                               for f in self.filters)
        return self._cached_filter_choices[filter_field]

    def apply_filters(self, queryset):
        for f in self.filters:
            queryset = f.apply_filter(queryset)
        return queryset

    def render_filter(self, filter_):
        field_obj = self.model._meta.get_field(filter_.field)
        choices = self.get_filter_choices(filter_.field)
        ctx = {'filterlabel': capfirst(field_obj.verbose_name)}
        ctx['choices'] = [dict(label=non_breaking_spaces(c.label),
                               url=u'?' + c.params.urlencode()
                                   if c.link_type != FILTER_DISPLAY else None,
                               link_type=c.link_type,
                               count=c.count)
                          for c in choices]
        return self.get_template(filter_.field).render(template.Context(ctx))

    def get_template(self, field_name):
        if self.template:
            return template.Template(self.template)
        else:
            return get_template(self.template_file)

    def render(self):
        return mark_safe(u'\n'.join(self.render_filter(f) for f in self.filters))

    def get_fields(self):
        return self.fields

    def get_filter_for_field(self, field):
        f, model, direct, m2m = self.model._meta.get_field_by_name(field)
        if f.rel is not None:
            if m2m:
                return ManyToManyFilter
            else:
                return ForeignKeyFilter
        elif f.choices:
            return ChoicesFilter
        else:
            type_ = f.get_internal_type()
            if type_ == 'DateField' or type_ == 'DateTimeField':
                return DateTimeFilter
            elif type_ == 'DecimalField' or type_ == 'FloatField':
                return NumericRangeFilter
            else:
                return ValuesFilter

    def setup_filters(self):
        filters = []
        for i, f in enumerate(self.get_fields()):
            klass = None
            if isinstance(f, six.string_types):
                opts = {}
                field_name = f
            else:
                opts = f[1]
                field_name = f[0]
                if len(f) > 2:
                    klass = f[2]
            if klass is None:
                klass = self.get_filter_for_field(field_name)
            filters.append(klass(field_name, self.model, self.params, **opts))
        return filters

    def make_title(self):
        if self.title_fields is None:
            title_fields = [filter_.field for filter_ in self.filters]
        else:
            title_fields = self.title_fields
        return u", ".join(c.label
                          for f in title_fields
                          for c in self.get_filter_choices(f)
                          if c.link_type == FILTER_REMOVE)

    def __str__(self):
        return self.render()
