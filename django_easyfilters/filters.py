from collections import namedtuple
from datetime import date
import operator
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import formats
from django.utils.datastructures import SortedDict
from django.utils.text import capfirst
from django_easyfilters.queries import date_aggregation

FILTER_ADD = 'add'
FILTER_REMOVE = 'remove'
FILTER_ONLY_CHOICE = 'only'

FilterChoice = namedtuple('FilterChoice', 'label count params link_type')


class Filter(object):
    """
    A Filter creates links/URLs that correspond to some DB filtering,
    and can apply the information from a URL to filter a QuerySet.
    """

    ### Public interface ###

    def __init__(self, field, model, params, query_param=None, order_by_count=False):
        self.field = field
        self.model = model
        self.params = params
        if query_param is None:
            query_param = field
        self.query_param = query_param
        self.order_by_count = order_by_count
        self.field_obj = self.model._meta.get_field(self.field)
        # Make chosen an immutable sequence, to stop accidental mutation.
        self.chosen = tuple(self.choices_from_params())

    def apply_filter(self, qs):
        """
        Apply the filtering defined in params (request.GET) to the queryset qs,
        returning the new QuerySet.
        """
        choices = list(self.chosen)
        while len(choices) > 0:
            lookup = self.lookup_from_choice(choices.pop())
            qs = qs.filter(**lookup)
        return qs

    def get_choices(self, qs):
        """
        Returns a list of namedtuples containing (label (as a string), count,
        params, link type)
        """
        raise NotImplementedError()

    ### Methods that are used by base implementation above ###

    def choices_from_params(self):
        out = []
        for p in self.params.getlist(self.query_param):
            try:
                choice = self.choice_from_param(p)
                out.append(choice)
            except ValueError:
                pass
        return out

    def choice_from_param(self, param):
        """
        Returns a native Python object representing something that has been
        chosen for a filter, converted from the string value in param.
        """
        try:
            return self.field_obj.to_python(param)
        except ValidationError:
            raise ValueError()

    def lookup_from_choice(self, choice):
        """
        Converts a choice value to a lookup dictionary that can be passed to
        QuerySet.filter() to do the filtering for that choice.
        """
        return {self.field: choice}

    ### Utility methods needed by most/all subclasses ###

    def param_from_choices(self, choices):
        """
        For a list of choices, return the parameter list that should be created.
        """
        return map(unicode, choices)

    def build_params(self, add=None, remove=None):
        """
        Builds a new parameter MultiDict.
        add is an optional item to add,
        remove is an option list of items to remove.
        """
        params = self.params.copy()
        chosen = list(self.chosen)
        if remove is not None:
            for r in remove:
                chosen.remove(r)
        else:
            if add not in chosen:
                chosen.append(add)
        if chosen:
            params.setlist(self.query_param, self.param_from_choices(chosen))
        else:
            del params[self.query_param]
        params.pop('page', None) # links should reset paging
        return params

    def sort_choices(self, qs, choices):
        """
        Sorts the choices by applying order_by_count if applicable.

        See also sort_choices_custom.
        """
        if self.order_by_count:
            choices.sort(key=operator.attrgetter('count'), reverse=True)
        else:
            choices = self.sort_choices_custom(qs, choices)
        return choices

    def sort_choices_custom(self, qs, choices):
        """
        Override this to provide a custom sorting method for a field. If sorting
        can be better done in the DB, it should be done in the get_choices_add
        method.
        """
        return choices


class SingleValueFilterMixin(object):

    def get_values_counts(self, qs):
        """
        Returns a SortedDict dictionary of {value: count}.

        The order is the underlying order produced by sorting ascending on the
        DB field.
        """
        values_counts = qs.values_list(self.field).order_by(self.field).annotate(models.Count(self.field))

        count_dict = SortedDict()
        for val, count in values_counts:
            count_dict[val] = count
        return count_dict

    def normalize_add_choices(self, choices):
        if len(choices) == 1 and not self.field_obj.null:
            # No point giving people a choice of one, since all the results will
            # already have the selected value (apart from nullable fields, which
            # might have null)
            choices = [FilterChoice(label=choices[0].label,
                                    count=choices[0].count,
                                    link_type=FILTER_ONLY_CHOICE,
                                    params=None)]
        return choices

    def get_choices(self, qs):
        choices_remove = self.get_choices_remove(qs)
        if len(choices_remove) > 0:
            return choices_remove
        else:
            choices_add = self.normalize_add_choices(self.get_choices_add(qs))
            return self.sort_choices(qs, choices_add)

    def get_choices_add(self, qs):
        raise NotImplementedError()

    def get_choices_remove(self, qs):
        chosen = self.chosen
        choices = []
        for choice in chosen:
            display = self.display_choice(choice)
            if display is not None:
                choices.append(FilterChoice(display,
                                            None, # Don't need count for removing
                                            self.build_params(remove=[choice]),
                                            FILTER_REMOVE))
        return choices


class ValuesFilter(SingleValueFilterMixin, Filter):
    """
    Fallback Filter for various kinds of simple values.
    """
    def display_choice(self, choice):
        retval = unicode(choice)
        if retval == u'':
            return u'(empty)'
        else:
            return retval

    def get_choices_add(self, qs):
        """
        Called by 'get_choices', this is usually the one to override.
        """
        count_dict = self.get_values_counts(qs)
        return [FilterChoice(self.display_choice(val),
                             count,
                             self.build_params(add=val),
                             FILTER_ADD)
                for val, count in count_dict.items()]


class ChoicesFilter(ValuesFilter):
    """
    Filter for fields that have 'choices' defined.
    """
    # Need to do the following:
    # 1) ensure we only display options that are in 'choices'
    # 2) ensure the order is the same as in choices
    # 3) make display value = the second element in choices' tuples.
    def __init__(self, *args, **kwargs):
        super(ChoicesFilter, self).__init__(*args, **kwargs)
        self.choices_dict = dict(self.field_obj.flatchoices)

    def display_choice(self, choice):
        # 3) above
        return self.choices_dict.get(choice, choice)

    def get_choices_add(self, qs):
        count_dict = self.get_values_counts(qs)
        choices = []
        for val, display in self.field_obj.choices:
            # 1), 2) above
            if val in count_dict:
                # We could use the value 'display' here, but for consistency
                # call display_choice() in case it is overriden.
                choices.append(FilterChoice(self.display_choice(val),
                                            count_dict[val],
                                            self.build_params(add=val),
                                            FILTER_ADD))
        return choices


class ForeignKeyFilter(SingleValueFilterMixin, Filter):
    """
    Filter for ForeignKey fields.
    """
    def __init__(self, field, model, params, **kwargs):
        self.field_obj = model._meta.get_field(field)
        self.rel_model = self.field_obj.rel.to
        self.rel_field = self.field_obj.rel.get_related_field()
        super(ForeignKeyFilter, self).__init__(field, model, params, **kwargs)

    def choice_from_param(self, param):
        try:
            return self.rel_field.to_python(param)
        except ValidationError:
            raise ValueError()

    def display_choice(self, choice):
        lookup = {self.rel_field.name: choice}
        try:
            obj = self.rel_model.objects.get(**lookup)
        except self.rel_model.DoesNotExist:
            return None
        return unicode(None)

    def get_choices_add(self, qs):
        count_dict = self.get_values_counts(qs)
        lookup = {self.rel_field.name + '__in': count_dict.keys()}
        objs = self.rel_model.objects.filter(**lookup)
        choices = []

        for o in objs:
            pk = getattr(o, self.rel_field.attname)
            choices.append(FilterChoice(unicode(o),
                                        count_dict[pk],
                                        self.build_params(add=pk),
                                        FILTER_ADD))
        return choices


class MultiValueFilterMixin(object):

    def get_choices(self, qs):
        # In general, can filter multiple times, so we can have multiple remove
        # links, and multiple add links, at the same time.
        choices_remove = self.get_choices_remove(qs)
        choices_add = self.get_choices_add(qs)
        choices_add = self.sort_choices(qs, choices_add)
        return choices_remove + choices_add


class ManyToManyFilter(MultiValueFilterMixin, Filter):
    def __init__(self, *args, **kwargs):
        super(ManyToManyFilter, self).__init__(*args, **kwargs)
        self.rel_model = self.field_obj.rel.to

    def choice_from_param(self, param):
        try:
            return self.field_obj.rel.get_related_field().to_python(param)
        except ValidationError:
            raise ValueError()

    def get_choices_add(self, qs):
        # It is easiest to base queries around the intermediate table, in order
        # to get counts.
        through = self.field_obj.rel.through
        rel_model = self.rel_model

        assert rel_model != self.model, "Can't cope with this yet..."

        fkey_to_this_table = [f for f in through._meta.fields
                              if f.rel is not None and f.rel.to is self.model][0]
        fkey_to_other_table = [f for f in through._meta.fields
                               if f.rel is not None and f.rel.to is rel_model][0]

        # We need to limit items by what is in the main QuerySet (which might
        # already be filtered).
        main_filter = {fkey_to_this_table.name + '__in':qs}
        m2m_objs = through.objects.filter(**main_filter)

        # We need to exclude items in other table that we have already filtered
        # on, because they are not interesting.
        exclude_filter = {fkey_to_other_table.name + '__in': self.chosen}
        m2m_objs = m2m_objs.exclude(**exclude_filter)

        # Now get counts:
        field_name = fkey_to_other_table.name
        values_counts = m2m_objs.values_list(field_name).order_by(field_name).annotate(models.Count(field_name))

        count_dict = SortedDict()
        for val, count in values_counts:
            count_dict[val] = count

        # Now, need to lookup objects on related table, to display them.
        objs = rel_model.objects.filter(pk__in=count_dict.keys())

        choices = []
        for o in objs:
            pk = o.pk
            choices.append(FilterChoice(unicode(o),
                                        count_dict[pk],
                                        self.build_params(add=pk),
                                        FILTER_ADD))
        return choices

    def get_choices_remove(self, qs):
        chosen = self.chosen
        # Do a query in bulk to get objs corresponding to choices.
        objs = self.rel_model.objects.filter(pk__in=chosen)

        # We want to preserve order of items in params, so use a dict:
        obj_dict = dict([(obj.pk, obj) for obj in objs])
        return [FilterChoice(unicode(obj_dict[choice]),
                             None, # Don't need count for removing
                             self.build_params(remove=[choice]),
                             FILTER_REMOVE)
                for choice in chosen if choice in obj_dict]


class DrillDownMixin(object):

    def get_choices_remove(self, qs):
        # Due to drill down, if a broader param is removed, the more specific
        # params must be removed too. We assume we can do an ordering on
        # whatever 'choice' objects are in chosen, and 'greater' means 'more
        # specific'.
        chosen = list(self.chosen)
        out = []
        for i, choice in enumerate(chosen):
            to_remove = [c for c in chosen if c >= choice]
            out.append(FilterChoice(self.display_choice(choice),
                                    None,
                                    self.build_params(remove=to_remove),
                                    FILTER_REMOVE))
        return out


DateRangeTypeBase = namedtuple('DateRangeTypeBase', 'level single label regex')
class DateRangeType(DateRangeTypeBase):

    all = {} # Keep a cache, so that we have unique instances

    def __init__(self, *args):
        super(DateRangeType, self).__init__(*args)
        DateRangeType.all[(self.level, self.single)] = self

    def to_single(self):
        """
        Return the same but with 'single=True'
        """
        return DateRangeType.all[(self.level, True)]

    def to_multi(self):
        """
        Return the same but with 'single=False'
        """
        return DateRangeType.all[(self.level, False)]

    def drilldown(self):
        if self is DAY:
            return None
        if not self.single:
            return self.to_single()
        else:
            # We always drill down to 'single', and then generate
            # ranges (i.e. multi) if appropriate.
            return DateRangeType.all[(self.level + 1, True)]

YEARGROUP   = DateRangeType(1, False, 'year',  re.compile(r'^(\d{4})..(\d{4})$'))
YEAR        = DateRangeType(1, True,  'year',  re.compile(r'^(\d{4})$'))
MONTHGROUP  = DateRangeType(2, False, 'month', re.compile(r'^(\d{4}-\d{2})..(\d{4}-\d{2})$'))
MONTH       = DateRangeType(2, True,  'month', re.compile(r'^(\d{4}-\d{2})$'))
DAYGROUP    = DateRangeType(3, False, 'day',   re.compile(r'^(\d{4}-\d{2}-\d{2})..(\d{4}-\d{2}-\d{2})$'))
DAY         = DateRangeType(3, True,  'day',   re.compile(r'^(\d{4}-\d{2}-\d{2})$'))


class DateChoice(object):
    """
    Represents a choice of date. Params are converted to this, and this is used
    to build new params and format links.

    It can represent a year, month or day choice, or a range (start, end, both
    inclusive) of any of these choice.
    """

    def __init__(self, range_type, values):
        self.range_type = range_type
        self.values = values

    def __unicode__(self):
        # This is called when converting to URL
        return '..'.join(self.values)

    def __repr__(self):
        return '<DateChoice %s %s>' % (self.range_type, self.__unicode__())

    def __cmp__(self, other):
        return cmp((self.range_type, self.values),
                   (other.range_type, other.values))

    def display(self):
        # Called for user presentable string
        if self.range_type.single:
            value = self.values[0]
            parts = value.split('-')
            if self.range_type == YEAR:
                return value
            elif self.range_type == MONTH:
                from django.utils.dates import MONTHS
                return unicode(MONTHS[int(parts[1])])
            elif self.range_type == DAY:
                return str(int(parts[-1]))
        else:
            return u'-'.join([DateChoice(self.range_type.to_single(),
                                         [val]).display()
                              for val in self.values])

    @staticmethod
    def datetime_to_value(range_type, dt):
        if range_type == YEAR:
            return '%04d' % dt.year
        elif range_type == MONTH:
            return '%04d-%02d' % (dt.year, dt.month)
        else:
            return '%04d-%02d-%02d' % (dt.year, dt.month, dt.day)

    @staticmethod
    def from_datetime(range_type, dt):
        return DateChoice(range_type, [DateChoice.datetime_to_value(range_type, dt)])

    @staticmethod
    def from_datetime_range(range_type, dt1, dt2):
        return DateChoice(range_type.to_multi(),
                          [DateChoice.datetime_to_value(range_type, dt1),
                           DateChoice.datetime_to_value(range_type, dt2)])

    @staticmethod
    def from_param(param):
        for drt in DateRangeType.all.values():
            m = drt.regex.match(param)
            if m is not None:
                return DateChoice(drt, list(m.groups()))

    def make_lookup(self, field_name):
        # It's easier to do this all using datetime comparisons, than have a
        # separate path for the single year/month/day case.
        if self.range_type.single:
            start, end = self.values[0], self.values[0]
        else:
            start, end = self.values

        start_parts = map(int, start.split('-'))
        end_parts = map(int, end.split('-'))
        if self.range_type.label == 'year':
            return {field_name + '__gte': date(start_parts[0], 1, 1),
                    field_name + '__lt': date(end_parts[0] + 1, 1, 1)}
        elif self.range_type.label == 'month':
            yearadd, nextmonth = divmod(end_parts[1] + 1, 12)
            return {field_name + '__gte': date(start_parts[0], start_parts[1], 1),
                    field_name + '__lt': date(end_parts[0] + yearadd, nextmonth, 1) }
        else:
            return {}


class DateTimeFilter(MultiValueFilterMixin, DrillDownMixin, Filter):

    def __init__(self, *args, **kwargs):
        self.max_links = kwargs.pop('max_links', 12)
        super(DateTimeFilter, self).__init__(*args, **kwargs)

    def choice_from_param(self, param):
        choice = DateChoice.from_param(param)
        if choice is None:
            raise ValueError()
        return choice

    def choices_from_params(self):
        choices = super(DateTimeFilter, self).choices_from_params()
        choices.sort()
        return choices

    def lookup_from_choice(self, choice):
        return choice.make_lookup(self.field)

    def display_choice(self, choice):
        return choice.display()

    def get_choices_add(self, qs):
        chosen = list(self.chosen)
        range_type = None

        if len(chosen) > 0:
            range_type = chosen[-1].range_type.drilldown()
            if range_type is None:
                return []

        if range_type is None:
            # Get some initial idea of range
            date_range = qs.aggregate(first=models.Min(self.field),
                                      last=models.Max(self.field))
            first = date_range['first']
            last = date_range['last']
            if first is None or last is None:
                # No values, can't drill down:
                return []
            if first.year == last.year:
                if first.month == last.month:
                    range_type = DAY
                else:
                    range_type = MONTH
            else:
                range_type = YEAR

        date_qs = qs.dates(self.field, range_type.label)
        results = date_aggregation(date_qs)

        if len(results) > self.max_links:
            # Fold results together
            div, mod = divmod(len(results), self.max_links)
            if mod != 0:
                div += 1
            date_choice_counts = []
            i = 0
            while i < len(results):
                group = results[i:i+div]
                count = sum(row[1] for row in group)
                # build range:
                choice = DateChoice.from_datetime_range(range_type,
                                                        group[0][0],
                                                        group[-1][0])
                date_choice_counts.append((choice, count))
                i += div
        else:
            date_choice_counts = [(DateChoice.from_datetime(range_type, dt), count)
                                  for dt, count in results]

        choices = []
        for date_choice, count in date_choice_counts:
            if date_choice in chosen:
                continue
            choices.append(FilterChoice(date_choice.display(),
                                        count,
                                        self.build_params(add=date_choice),
                                        FILTER_ADD))
        return choices
