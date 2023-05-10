# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from absl.testing import absltest
from absl.testing import parameterized
import numpy as np
import pandas as pd
import xarray

import xarray_tensorstore


class XarrayTensorstoreTest(parameterized.TestCase):

  @parameterized.named_parameters(
      # TODO(shoyer): consider using hypothesis to convert these into
      # property-based tests
      {
          'testcase_name': 'base',
          'transform': lambda ds: ds,
      },
      {
          'testcase_name': 'transposed',
          'transform': lambda ds: ds.transpose('z', 'x', 'y'),
      },
      {
          'testcase_name': 'basic_int',
          'transform': lambda ds: ds.isel(y=1),
      },
      {
          'testcase_name': 'negative_int',
          'transform': lambda ds: ds.isel(y=-1),
      },
      {
          'testcase_name': 'basic_slice',
          'transform': lambda ds: ds.isel(z=slice(2)),
      },
      {
          'testcase_name': 'full_slice',
          'transform': lambda ds: ds.isel(z=slice(0, 4)),
      },
      {
          'testcase_name': 'out_of_bounds_slice',
          'transform': lambda ds: ds.isel(z=slice(0, 10)),
      },
      {
          'testcase_name': 'strided_slice',
          'transform': lambda ds: ds.isel(z=slice(0, None, 2)),
      },
      {
          'testcase_name': 'negative_stride_slice',
          'transform': lambda ds: ds.isel(z=slice(None, None, -1)),
      },
      {
          'testcase_name': 'repeated_indexing',
          'transform': lambda ds: ds.isel(z=slice(1, None)).isel(z=0),
      },
      {
          'testcase_name': 'oindex',
          # includes repeated, negative and out of order indices
          'transform': lambda ds: ds.isel(x=[0], y=[1, 1], z=[1, -1, 0]),
      },
      {
          'testcase_name': 'vindex',
          'transform': lambda ds: ds.isel(x=('w', [0, 1]), y=('w', [1, 2])),
      },
      {
          'testcase_name': 'mixed_indexing_types',
          'transform': lambda ds: ds.isel(x=0, y=slice(2), z=[-1]),
      },
      {
          'testcase_name': 'select_a_variable',
          'transform': lambda ds: ds['foo'],
      },
  )
  def test_open_zarr(self, transform):
    source = xarray.Dataset(
        {
            'foo': (('x',), np.arange(2), {'local': 'local metadata'}),
            'bar': (('x', 'y'), np.arange(6).reshape(2, 3)),
            'baz': (('x', 'y', 'z'), np.arange(24).reshape(2, 3, 4)),
        },
        coords={
            'x': [1, 2],
            'y': pd.to_datetime(['2000-01-01', '2000-01-02', '2000-01-03']),
            'z': ['a', 'b', 'c', 'd'],
        },
        attrs={'global': 'global metadata'},
    )
    path = self.create_tempdir().full_path
    source.chunk().to_zarr(path)

    expected = transform(source)
    actual = transform(xarray_tensorstore.open_zarr(path)).compute()
    xarray.testing.assert_identical(actual, expected)

  def test_open_zarr_from_uri(self):
    source = xarray.Dataset(
        {'baz': (('x', 'y', 'z'), np.arange(24).reshape(2, 3, 4))}
    )
    path = self.create_tempdir().full_path
    source.chunk().to_zarr(path)

    opened = xarray_tensorstore.open_zarr('file://' + path)
    xarray.testing.assert_identical(source, opened)

  def test_read_dataset(self):
    source = xarray.Dataset(
        {'baz': (('x', 'y', 'z'), np.arange(24).reshape(2, 3, 4))},
        coords={'x': np.arange(2)},
    )
    path = self.create_tempdir().full_path
    source.chunk().to_zarr(path)

    opened = xarray_tensorstore.open_zarr(path)
    read = xarray_tensorstore.read(opened)

    self.assertIsNone(opened.variables['baz']._data.future)
    self.assertIsNotNone(read.variables['baz']._data.future)
    xarray.testing.assert_identical(read, source)

  def test_read_dataarray(self):
    source = xarray.DataArray(
        np.arange(24).reshape(2, 3, 4),
        dims=('x', 'y', 'z'),
        name='baz',
        coords={'x': np.arange(2)},
    )
    path = self.create_tempdir().full_path
    source.to_dataset().chunk().to_zarr(path)

    opened = xarray_tensorstore.open_zarr(path)['baz']
    read = xarray_tensorstore.read(opened)

    self.assertIsNone(opened.variable._data.future)
    self.assertIsNotNone(read.variable._data.future)
    xarray.testing.assert_identical(read, source)


if __name__ == '__main__':
  absltest.main()
  