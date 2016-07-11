#!/usr/bin/env python3
"""


"""

import nagiosplugin
import json
import requests
import argparse


class FfsRouterStatus(nagiosplugin.Resource):
  def __init__(self, url, router_name):
    self.url = url
    self.router_name = router_name

  def probe(self):
    try:
      r = requests.get(self.url)
      r.raise_for_status()
    except requests.RequestException as e:
      raise nagiosplugin.CheckError(e)
  
    try:
      j = json.loads(r.text)
    except json.JSONDecodeError as e:
      raise nagiosplugin.CheckError(e)
  
    for router in j['nodes']:
      if self.router_name == router['name']:
        yield nagiosplugin.Metric('online', (router['flags']['online'], router['name'], router['id']))
        yield nagiosplugin.Metric('clients', router['clientcount'], min=0)
        return


class FfsRouterContext(nagiosplugin.Context):
  def __init__(self, context):
    super(FfsRouterContext, self).__init__(context)

  def evaluate(self, metric, resource):
    online, name, rid = metric.value
    output = 'router \'%s\' (%s) is %s' % (name, rid, 'online' if online else 'offline')
    if online:
      return self.result_cls(nagiosplugin.Ok, metric=metric, hint=output)
    else:
      return self.result_cls(nagiosplugin.Critical, metric=metric, hint=output)


def main():
  argp = argparse.ArgumentParser()
  required = argp.add_argument_group('required named arguments')
  required.add_argument('-u', '--url', help='where to get status json from', required=True)
  required.add_argument('-n', '--name', help='router to check', required=True)
  argp.add_argument('-w', '--warning', metavar='RANGE', default='40', type=int,
                    help='return warning if clients is outside RANGE')
  argp.add_argument('-c', '--critical', metavar='RANGE', default='50', type=int,
                    help='return critical if clients load is outside RANGE')
  args = argp.parse_args()

  check = nagiosplugin.Check(
    FfsRouterStatus(args.url, args.name),
    FfsRouterContext('online'),
    nagiosplugin.ScalarContext('clients', args.warning, args.critical, fmt_metric='{value} clients using this router')
  )
  check.main()

if __name__ == '__main__':
  main()
