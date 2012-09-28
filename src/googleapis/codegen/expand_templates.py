#!/usr/bin/python2.6
# Copyright 2011 Google Inc. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


__author__ = 'aiuto@google.com (Tony Aiuto)'

import json
import os

from google.apputils import app
import gflags as flags
from googleapis.codegen import generator
from googleapis.codegen import generator_lookup
from googleapis.codegen import language_model
from googleapis.codegen.api import Api
from googleapis.codegen.filesystem_library_package import FilesystemLibraryPackage
from googleapis.codegen.targets import Targets
from googleapis.codegen.zip_library_package import ZipLibraryPackage

FLAGS = flags.FLAGS

flags.DEFINE_string(
    'discovery',
    None,
    'A discovery document captured from a discovery service.')
flags.DEFINE_boolean(
    'include_timestamp',
    False,
    'Adds a timestamp to the generated source files.')
flags.DEFINE_enum(
    'language',
    'any',
    ['any'] + generator_lookup.SupportedLanguages(),
    'Target language for the generated code')
flags.DEFINE_string(
    'language_variant',
    'default',
    'which variant of "language" to generate for. E.g. "stable" vs. "head".')
flags.DEFINE_string(
    'output_dir',
    None,
    'A path to a directory where the generated files will be created.')
flags.DEFINE_string(
    'output_file',
    None,
    'An output file path to contain the .zip archive for the generated code.')
flags.DEFINE_enum(
    'output_type',
    'plain',
    ['plain', 'full'],
    'What kind of output to make.'
    ' plain=just the source,'
    ' full=turn on all the optional parts (useful for testing the generator).'
    )
flags.DEFINE_string(
    'templates',
    None,
    'The name of the template suite (w.r.t. language and variant)')
flags.DEFINE_bool('version_package', False, 'Put API version in package paths')

flags.DECLARE_key_flag('discovery')
flags.DECLARE_key_flag('include_timestamp')
flags.DECLARE_key_flag('language')
flags.DECLARE_key_flag('language_variant')
flags.DECLARE_key_flag('output_dir')
flags.DECLARE_key_flag('output_file')
flags.DECLARE_key_flag('output_type')
flags.DECLARE_key_flag('templates')
flags.DECLARE_key_flag('version_package')


def main(unused_argv):
  if not FLAGS.discovery:
    raise app.UsageError('You must specify --discovery')
  if not (FLAGS.output_dir or FLAGS.output_file):
    raise app.UsageError(
        'You must specify one of --output_dir or --output_file')
  if not FLAGS.templates:
    raise app.UsageError('You must specify --templates')

  f = open(FLAGS.discovery)
  discovery_doc = json.loads(f.read())
  f.close()

  options = {
      # Include other files needed to compile (e.g. base jar files)
      'include_dependencies': False,
      # Include the timestamp in the generated library
      'include_timestamp': FLAGS.include_timestamp,
      # Put API version in the package
      'version_package': FLAGS.version_package,
      }
  if FLAGS.output_type == 'full':
    options['include_dependencies'] = True

  # Instantiate the right code generator
  try:
    if FLAGS.language == 'any':
      api = Api(discovery_doc)
      # TODO(user): A default language model should be built in to the
      #   templates
      lm = language_model.DocumentingLanguageModel()
      api.VisitAll(lambda o: o.SetLanguageModel(lm))
    else:
      generator_class = generator_lookup.GetGeneratorByLanguage(FLAGS.language)
      api = generator_class(discovery_doc).api

  except ValueError:
    raise app.UsageError('Unsupported language option: %s' % FLAGS.language)

  gen = TemplateExpander(api, options=options)

  # Get the path to the template set.
  language_variants = Targets().VariationsForLanguage(FLAGS.language)
  if language_variants:
    template_dir = language_variants.AbsoluteTemplateDir(FLAGS.language_variant)
    features = language_variants.GetFeatures(FLAGS.language_variant)
    gen.SetFeatures(features)
  else:
    template_dir = os.path.join(template_dir, FLAGS.language)
  template_dir = os.path.join(template_dir, FLAGS.templates)
  gen.SetTemplateDir(template_dir)

  # Get an output writer
  if FLAGS.output_dir:
    package_writer = FilesystemLibraryPackage(FLAGS.output_dir)
  else:
    out = open(FLAGS.output_file, 'w')
    package_writer = ZipLibraryPackage(out)

  # do it
  gen.GeneratePackage(package_writer)
  package_writer.DoneWritingArchive()
  if FLAGS.output_file:
    out.close()
  return 0


class TemplateExpander(generator.TemplateGenerator):

  def __init__(self, api, options=None):
    super(TemplateExpander, self).__init__(options=options)
    self._api = api

  def GeneratePackage(self, package_writer):
    """Walk the templates and generate output.

    Overrides the default.

    Args:
      package_writer: (LibraryPackage) output package
    """
    variables = {
        'api': self._api,
        'options': self._options,
        }
    self.WalkTemplateTree('.', {}, {}, variables, package_writer)


if __name__ == '__main__':
  app.run()
