
"""
    This module handles exposing user types for metrics processing.
"""

__author__ = "ryan faulkner"
__date__ = "01/28/2013"
__email__ = 'rfaulkner@wikimedia.org'

from user_metrics.config import logging, settings

from user_metrics.etl.data_loader import Connector
from dateutil.parser import parse as date_parse
from datetime import datetime, timedelta

MEDIAWIKI_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"


def get_latest_cohort_id():
    """
        Generates an ID for the next usertag cohort

        Returns an integer one greater than the current greatest
        usertag_meta ID
    """
    sql = \
        """
            SELECT max(utm_id)
            FROM %(cohort_meta_instance)s.%(cohort_meta_db)s
        """
    sql %= {
        'cohort_meta_instance': settings.__cohort_meta_instance__,
        'cohort_meta_db': settings.__cohort_meta_db__,
    }
    conn = Connector(instance=settings.__cohort_data_instance__)
    conn._cur_.execute(sql)
    max_id = conn._cur_.fetchone()[0]
    del conn

    return int(max_id) + 1


def generate_test_cohort(project,
                         max_size=10,
                         write=False,
                         user_interval_size=1,
                         rev_interval_size=7,
                         rev_lower_limit=0):
    """
        Build a test cohort (list of UIDs) for the given project.

        Parameters
        ~~~~~~~~~~

        project : str
           Wikipedia project e.g. 'enwiki'.

        size : uint
           Number of users to include in the cohort.

        write: boolean
           Flag indicating whether to write the cohort to
           settings.__cohort_meta_db__ and settings.__cohort_db__.

        user_interval_size: uint
            Number of days within which to take registered users

        rev_lower_limit: int
            Minimum number of revisions a user must have between registration
            and the

        Returns the list of UIDs from the corresponding project that defines
        the test cohort.
    """

    # Determine the time bounds that define the cohort acceptance criteria

    ts_start_o = datetime.now() + timedelta(days=-60)
    ts_end_user_o = ts_start_o + timedelta(days=user_interval_size)
    ts_end_revs_o = ts_start_o + timedelta(days=rev_interval_size)

    ts_start = MediaWikiUser()._format_mediawiki_timestamp(ts_start_o)
    ts_end_user = MediaWikiUser()._format_mediawiki_timestamp(ts_end_user_o)
    ts_end_revs = MediaWikiUser()._format_mediawiki_timestamp(ts_end_revs_o)

    # Synthesize query and execute
    logging.info(__name__ + ':: Getting users from {0}.\n\n'
                            '\tUser interval: {1} - {2}\n'
                            '\tRevision interval: {1} - {3}\n'
                            '\tMax users = {4}\n'
                            '\tMin revs = {5}\n'.
                            format(project, str(ts_start_o)[:19],
                                   str(ts_end_user_o)[:19],
                                   str(ts_end_revs_o)[:19],
                                   max_size,
                                   rev_lower_limit
                                   )
                 )
    sql = \
        """
            SELECT
                rev_user,
                COUNT(*) as revs
            FROM
                %(project)s.revision
            WHERE
                rev_user IN (
                    SELECT user_id
                    FROM %(project)s.user
                    WHERE user_registration > '%(ts_start)s'
                        AND user_registration < '%(ts_end_user)s')
                AND rev_timestamp > '%(ts_start)s'
                AND rev_timestamp <= '%(ts_end_revs)s'
            GROUP BY 1
            HAVING revs > %(rev_lower_limit)s
            ORDER BY 2 DESC
            LIMIT %(max_size)s;
        """
    sql %= {
        'project': project,
        'ts_start': ts_start,
        'ts_end_user': ts_end_user,
        'ts_end_revs': ts_end_revs,
        'max_size': max_size,
        'rev_lower_limit': rev_lower_limit,
    }
    conn = Connector(instance=settings.PROJECT_DB_MAP[project])
    conn._cur_.execute(sql)
    users = [row for row in conn._cur_]
    del conn

    # get latest cohort id
    utm_id = get_latest_cohort_id()

    # add new ids to
    if write:
        logging.info(__name__ + ':: ')

    return users


class MediaWikiUserException(Exception):
    """ Basic exception class for UserMetric types """
    def __init__(self, message="Error obtaining user(s) from MediaWiki "
                               "instance."):
        Exception.__init__(self, message)


class MediaWikiUser(object):
    """
        Class to expose users from MediaWiki databases in a standard way.
        A class level attribute QUERY_TYPES handles the method in which
        the user is extracted from a MediaWiki DB.
    """

    # Queries MediaWiki database for account creations via Logging table
    USER_QUERY_LOG = """
                    SELECT log_user
                    FROM %(project)s.logging
                    WHERE log_timestamp > %(date_start)s AND
                     log_timestamp <= %(date_end)s AND
                     log_action = 'create' AND log_type='newusers'
                """

    # Queries MediaWiki database for account creations via User table
    USER_QUERY_USER = """
                    SELECT user_id
                    FROM %(project)s.user
                    WHERE user_registration > %(date_start)s AND
                     user_registration <= %(date_end)s
                """

    QUERY_TYPES = {
        1: USER_QUERY_LOG,
        2: USER_QUERY_USER,
    }

    def __init__(self, query_type=1):
        self._query_type = query_type
        super(MediaWikiUser, self).__init__()

    def _format_mediawiki_timestamp(self, timestamp_repr):
        """ Convert to mediawiki timestamps """
        if hasattr(timestamp_repr, 'strftime'):
            return timestamp_repr.strftime(MEDIAWIKI_TIMESTAMP_FORMAT)
        else:
            return date_parse(timestamp_repr).strftime(
                MEDIAWIKI_TIMESTAMP_FORMAT)

    def get_users(self, date_start, date_end, project='enwiki'):
        """
            Returns a Generator for MediaWiki user IDs.
        """
        param_dict = {
            'date_start': self._format_mediawiki_timestamp(date_start),
            'date_end': self._format_mediawiki_timestamp(date_end),
            'project': project,
        }
        conn = Connector(instance=settings.__cohort_data_instance__)
        conn._cur_.execute(self.QUERY_TYPES[self._query_type] % param_dict)

        for row in conn._cur_:
            yield row[0]
