#!/usr/bin/python
"""
Copyright 2016 Google Inc. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import gzip
import json
import logging
import os

########################################################################################################################
#   Trace processing
########################################################################################################################
class Trace():
  def __init__(self):
    self.thread_stack = {}
    self.main_thread = None
    self.ignore_threads = {}
    self.threads = {}
    self.user_timing = []
    return

  def Process(self, trace):
    f = None
    self.__init__()
    try:
      file_name, ext = os.path.splitext(trace)
      if ext.lower() == '.gz':
        f = gzip.open(trace, 'rb')
      else:
        f = open(trace, 'r')
      for line in f:
        line = line.strip("\r\n\t ,")
        try:
          trace_event = json.loads(line)
          if 'traceEvents' in trace_event:
            for sub_event in trace_event['traceEvents']:
              self.ProcessEvent(sub_event)
          else:
            self.ProcessEvent(trace_event)
        except:
          pass

    except:
      logging.critical("Error processing trace " + trace)

    if f is not None:
      f.close()

  def WriteUserTiming(self, file):
    try:
      if len(self.user_timing):
        file_name, ext = os.path.splitext(file)
        if ext.lower() == '.gz':
          with gzip.open(file, 'wb') as f:
            json.dump(self.user_timing, f)
        else:
          with open(file, 'w') as f:
            json.dump(self.user_timing, f)
    except:
      logging.critical("Error writing user timing to " + file)

  def ProcessEvent(self, trace_event):
    if 'cat' in trace_event and 'name' in trace_event and 'ts' in trace_event:
      if trace_event['cat'] == 'blink.user_timing':
        self.user_timing.append(trace_event)
      elif 'pid' in trace_event and 'tid' in trace_event and 'ph' in trace_event and\
              trace_event['cat'].find('devtools.timeline') >= 0:
        thread = '{0}:{1}'.format(trace_event['pid'], trace_event['tid'])

        # Keep track of the main thread
        if self.main_thread is None and trace_event['name'] == 'ResourceSendRequest' and 'args' in trace_event and\
                'data' in trace_event['args'] and 'url' in trace_event['args']['data']:
          if trace_event['args']['data']['url'][:21] == 'http://127.0.0.1:8888':
            self.ignore_threads[thread] = True
          else:
            if thread not in self.threads:
              self.threads[thread] = len(self.threads)
            self.main_thread = thread
            if 'dur' not in trace_event:
              trace_event['dur'] = 1

        # Make sure each thread has a numerical ID
        if self.main_thread is not None and thread not in self.threads and thread not in self.ignore_threads and\
                trace_event['name'] != 'Program':
          self.threads[thread] = len(self.threads)

        # Build timeline events on a stack. 'B' begins an event, 'E' ends an event
        if (thread in self.threads and ('dur' in trace_event or trace_event['ph'] == 'B' or trace_event['ph'] == 'E')):
          trace_event['thread'] = self.threads[thread]
          if thread not in self.thread_stack:
            self.thread_stack[thread] = []
          e = None
          if trace_event['ph'] == 'E':
            if len(self.thread_stack[thread]) > 0:
              e = self.thread_stack[thread].pop()
              if e['name'] == trace_event['name']:
                e['tsEnd'] = trace_event['ts']
          else:
            e = trace_event
            e['type'] = e['name']
            e['tsStart'] = e['ts']
            if e['ph'] == 'B':
              self.thread_stack[thread].append(e)
            elif 'dur' in e:
              e['tsEnd'] = e['tsStart'] + e['dur']

          if e is not None:
            # attach it to a parent event if there is one
            if len(self.thread_stack[thread]) > 0:
              parent = self.thread_stack[thread].pop()
              if 'children' not in parent:
                parent['children'] = []
              parent['children'].append(e)
              self.thread_stack[thread].append(parent)
            else:
              self.ProcessTimelineEvent(e)

  def ProcessTimelineEvent(self, e):
    return

########################################################################################################################
#   Main Entry Point
########################################################################################################################
def main():
  import argparse
  parser = argparse.ArgumentParser(description='Chrome trace parser.',
                                   prog='trace-parser')
  parser.add_argument('-v', '--verbose', action='count',
                      help="Increase verbosity (specify multiple times for more). -vvvv for full debug output.")
  parser.add_argument('-t', '--trace', help="Input trace file.")
  parser.add_argument('-c', '--cpu', help="Output CPU time slices file.")
  parser.add_argument('-b', '--breakdown', help="Output cpu breakdown file.")
  parser.add_argument('-u', '--user', help="Output user timing file.")
  options = parser.parse_args()

  if not options.trace:
    parser.error("Input trace file is not specified.")

  trace = Trace()
  trace.Process(options.trace)

  if options.user:
    trace.WriteUserTiming(options.user)

  # Set up logging
  log_level = logging.CRITICAL
  if options.verbose == 1:
    log_level = logging.ERROR
  elif options.verbose == 2:
    log_level = logging.WARNING
  elif options.verbose == 3:
    log_level = logging.INFO
  elif options.verbose >= 4:
    log_level = logging.DEBUG
  logging.basicConfig(level=log_level, format="%(asctime)s.%(msecs)03d - %(message)s", datefmt="%H:%M:%S")


if '__main__' == __name__:
  main()
