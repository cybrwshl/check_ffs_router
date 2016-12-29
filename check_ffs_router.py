#!/usr/bin/env python3
"""


"""

import nagiosplugin
import json
import requests
import argparse
import portalocker
import tempfile
import os
import time
from datetime import datetime


TEMP_DIR  = tempfile.gettempdir()
JSON_FILE_PATH = os.path.join(TEMP_DIR, 'ffs-nodes.json')

DEFAULT_CHECK_INTERVAL      = 5  # minutes
DEFAULT_FILE_ACCESS_TIMEOUT = 1  # minutes


class FfsRouterStatus(nagiosplugin.Resource):
  def __init__(self, url, router_name):
    self.url = url
    self.router_name = router_name

  def get_json(self):
    if os.path.exists(JSON_FILE_PATH) and os.path.isfile(JSON_FILE_PATH):
      mod_time  = datetime.fromtimestamp(os.path.getmtime(JSON_FILE_PATH))
      time_diff = datetime.now() - mod_time
      time_diff = round(time_diff.total_seconds() / 60)

      if time_diff < DEFAULT_CHECK_INTERVAL:
        with open(JSON_FILE_PATH) as json_file:
          return json_file.read()

    # file is too old or does not exist
    with open(JSON_FILE_PATH, 'wb') as json_file:
      #portalocker.lock(json_file, portalocker.LOCK_EX)
      response = requests.get(self.url, stream=True)

      try:
        response.raise_for_status()
      except requests.RequestException as e:
        raise nagiosplugin.CheckError(e)

      for block in response.iter_content(1024):
        json_file.write(block)

    with open(JSON_FILE_PATH) as json_file:
      return json_file.read()

  def probe(self):
    try:
      json_content = json.loads(self.get_json())
    except json.JSONDecodeError as e:
      raise nagiosplugin.CheckError(e)

    for router in json_content['nodes']:

      # software, network, location, node_id, hostname, hardware
      nodeinfo = router['nodeinfo']

      # online, uplink
      flags = router['flags']

      # memory_usage, rootfs_usage, wireless, gateway_nexthop, clients,
      # loadavg, gateway, uptime
      statistics = router['statistics']

      if self.router_name == nodeinfo['hostname']:
        yield nagiosplugin.Metric('online', (flags['online'], 
            nodeinfo['hostname'], nodeinfo['node_id']))

        if flags['online'] == 'true':
          yield nagiosplugin.Metric('clients', statistics['clients'], min=0)
        return


class FfsRouterContext(nagiosplugin.Context):
  def __init__(self, context):
    super(FfsRouterContext, self).__init__(context)

  def evaluate(self, metric, resource):
    online, name, rid = metric.value
    output = 'router \'%s\' (%s) is %s' % \
            (name, rid, 'online' if online else 'offline')
    if online:
      return self.result_cls(nagiosplugin.Ok, metric=metric, hint=output)
    else:
      return self.result_cls(nagiosplugin.Critical, metric=metric, hint=output)


def main():
  argp = argparse.ArgumentParser()
  required = argp.add_argument_group('required named arguments')
  required.add_argument('-u', '--url', help='where to get status json from', 
          required=True)
  required.add_argument('-n', '--name', help='router to check', required=True)
  argp.add_argument('-w', '--warning', metavar='RANGE', default='40', type=int, 
          help='return warning if clients is outside RANGE')
  argp.add_argument('-c', '--critical', metavar='RANGE', default='50', type=int,
          help='return critical if clients load is outside RANGE')
  args = argp.parse_args()

  check = nagiosplugin.Check(
    FfsRouterStatus(args.url, args.name),
    FfsRouterContext('online'),
    nagiosplugin.ScalarContext('clients', args.warning, args.critical, 
        fmt_metric='{value} clients using this router')
  )
  check.main()

if __name__ == '__main__':
  main()

