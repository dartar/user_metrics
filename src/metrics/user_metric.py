"""

This module will be used to define Wikimedia Foundation user metrics.  The Strategy behavioural pattern
(http://en.wikipedia.org/wiki/Strategy_pattern) will be used to implement the metrics generation.  In general
the UserMetric type utilizes the process() function attribute to produce an internal list of metrics for a specified
set of user handles (typically ID but user names may also be specified) passed to the method on call. The execution of
process() produces a nested list that can be accessed via generator with an object call to __iter__().

The class structure is generally as follows: ::

    class Metric(object):

        def __init__(self):
            # initialize base metric

            return

        def process(self):
            # base metric implementation

            return metric_value


    class DerivedMetric(Metric):

        def __init__(self):
            super(DerivedMetric, self)

            # initialize derived metric

            return

        def process(self):
            # derived metric implementation

            return metric_value


These metrics will be used to support experimentation and measurement at the Wikimedia Foundation.  The guidelines for
this development may be found at https://meta.wikimedia.org/wiki/Research:Metrics.

"""

__author__ = "Ryan Faulkner"
__date__ = "July 27th, 2012"
__license__ = "GPL (version 2 or later)"

import src.etl.data_loader as dl
import MySQLdb
from collections import namedtuple
from dateutil.parser import parse as date_parse

class UserMetric(object):

    ALL_NAMESPACES = 'all_namespaces'
    DATETIME_STR_FORMAT = "%Y%m%d%H%M%S"
    _static_conn = None

    def __init__(self,
                 project='enwiki',
                 namespace=ALL_NAMESPACES,
                 **kwargs):

        self._data_source_ = dl.Connector(instance='slave')
        self._results = []
        self._project_ = project

        if not namespace == self.ALL_NAMESPACES:
            if not hasattr(namespace, '__iter__'): namespace = [namespace]
            self._namespace_ = set(namespace)
        else:
            self._namespace_ = namespace

    def __str__(self): return "\n".join([str(self._data_source_._db_), str(self.__class__),
                                         str(self._namespace_), self._project_])

    def __iter__(self): return (r for r in self._results)

    def __del__(self):
        if hasattr(self, '_data_source_') and hasattr(self._data_source_, 'close_db'):
            self._data_source_.close_db()

    @classmethod
    def get_static_connection(cls):
        if cls._static_conn is None:
            cls._static_conn = dl.Connector(instance='slave')
        return cls._static_conn._db_

    @classmethod
    def _construct_data_point(cls): return namedtuple(cls.__name__, cls.header())

    @classmethod
    def _get_timestamp(cls, ts_representation):
        """
            Helper method.  Takes a representation of a date object (String or datetime.datetime object) and formats
            as a timestamp: "YYYY-MM-DD HH:II:SS"

            - Parameters:
                - *date_representation* - String or datetime.  A formatted timestamp representation

            - Return:
                - String.  Timestamp derived from argument in format "YYYY-MM-DD HH:II:SS".
        """

        try:
            datetime_obj = date_parse(ts_representation[:19]) # timestamp strings should
        except AttributeError:
            datetime_obj = ts_representation
        except TypeError:
            datetime_obj = ts_representation

        # datetime_obj
        try:
            timestamp = datetime_obj.strftime(cls.DATETIME_STR_FORMAT)
            return timestamp
        except ValueError:
            raise cls.UserMetricError(message='Could not parse timestamp: %s' % datetime_obj.__str__())

    @classmethod
    def _escape_var(cls, var):
        """
            Escapes either elements of a list (recursively visiting elements) or a single variable.  The variable
            is cast to string before being escaped.

            - Parameters:
                - **var**: List or string.  Variable or list (potentially nested) of variables to be escaped.

            - Return:
                - List or string.  escaped elements.
        """

        # If the input is a list recursively call on elements
        if hasattr(var, '__iter__'):
            escaped_var = list()
            for elem in var: escaped_var.append(cls._escape_var(elem))
            return escaped_var
        else:
            return MySQLdb.escape_string(str(var))

    @classmethod
    def _format_namespace(cls, namespace):
        # format the namespace condition
        ns_cond = ''
        if hasattr(namespace, '__iter__'):
            if len(namespace) == 1:
                ns_cond = 'page_namespace = ' + str(namespace.pop())
            else:
                ns_cond = 'page_namespace in (' + ",".join(dl.DataLoader().cast_elems_to_string(list(namespace))) + ')'
        return ns_cond

    @staticmethod
    def header(): raise NotImplementedError

    def process(self, user_handle, is_id=True, **kwargs): raise NotImplementedError

    class UserMetricError(Exception):
        """ Basic exception class for UserMetric types """
        def __init__(self, message="Unable to process results using strategy."):
            Exception.__init__(self, message)