# -*- coding: utf-8 -*-
"""
Common code for the tests.
All tests using locust.io will need to create a HttpLocust class and run
the tests doing:

    from user import launch
    launch(classname, n_clients, rate, run_time):

"""
from __future__ import print_function, unicode_literals

import datetime
import gevent
import inspect
import os

from argparse import Namespace
from locust.runners import LocalLocustRunner
from locust import events, runners
from locust.stats import print_error_report, print_percentile_stats, print_stats, write_stat_csvs, stats_writer
from locust.log import setup_logging


def spawn_run_time_limit_greenlet(options):
    """
    To stop each test gevent greenlet after timeout passes
    """
    def timelimit_stop():
        runners.locust_runner.stop()
    gevent.spawn_later(options.run_time, timelimit_stop)


def shutdown(options, code=0):
    """
    Shut down locust by firing quitting event, printing/writing stats and exiting
    """
    if runners.locust_runner is not None:
        runners.locust_runner.stop()

    events.quitting.fire(reverse=True)
    print_stats(runners.locust_runner.request_stats)
    print_percentile_stats(runners.locust_runner.request_stats)
    if options.csvfilebase:
        write_stat_csvs(options.csvfilebase)
    print_error_report()


def get_test_calling():
    """
    Finds out the name of the test being run
    :returns: A string with the name of the module importing this module
    """
    frame_records = inspect.stack()[3]
    return inspect.getmodulename(frame_records[1])


def get_csv_filename():
    """
    Returns the filename for the csv stats export
    :returns: A string with the filename for the csv stats export
    """
    calling_module = get_test_calling()
    timestamp = datetime.datetime.now().strftime('%Y_%m_%d__%H_%M_%S__%f')
    return '{timestamp}_{mod}'.format(mod=calling_module, timestamp=timestamp)


def get_or_create_output_dir():
    """
    Gets or creates output directory in which to store the locust reports
    """
    output_dir = os.path.join('output', 'locust')

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir


def launch(classname, base_url, n_clients, rate, n_requests=None, timeout=600):
    """
    Launches the tests
    :param: classname: class inherited from HttpLocust defining the test
    :param: base_url: server and port of the url to request
    :param: n_clients: Number of concurrent users
    :param: rate: The rate per second in which clients are spawned
    :param: n_requests: Total number of requests to be done
    :param: timeout: Stop testing after the specified amount of seconds
    """
    options = Namespace(**{
        'host': base_url,
        'num_clients': n_clients,
        'hatch_rate': rate,
        'num_requests': n_requests if n_requests else n_clients * 10,
        'run_time': timeout,
        'no_web': True,
        'no_reset_stats': True,
        'csvfilebase': os.path.join(get_or_create_output_dir(), get_csv_filename())
    })

    setup_logging('INFO', None)
    runners.locust_runner = LocalLocustRunner([classname], options)

    # spawn client spawning/hatching greenlets:
    runners.locust_runner.start_hatching(wait=True)
    main_greenlet = runners.locust_runner.greenlet
    spawn_run_time_limit_greenlet(options)

    if options.csvfilebase:
        gevent.spawn(stats_writer, options.csvfilebase)
    try:
        main_greenlet.join()
        code = 0
        if len(runners.locust_runner.errors):
            code = 1
        shutdown(options, code=code)
    except KeyboardInterrupt:
        shutdown(options, 0)
