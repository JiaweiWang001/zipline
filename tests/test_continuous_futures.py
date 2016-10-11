#
# Copyright 2016 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from textwrap import dedent

import pandas as pd
from pandas import Timestamp, DataFrame

from zipline import TradingAlgorithm
from zipline.testing.fixtures import (
    WithCreateBarData,
    WithSimParams,
    ZiplineTestCase,
)


class ContinuousFuturesTestCase(WithCreateBarData,
                                WithSimParams,
                                ZiplineTestCase):

    START_DATE = pd.Timestamp('2015-01-05', tz='UTC')
    END_DATE = pd.Timestamp('2016-10-19', tz='UTC')

    SIM_PARAMS_START = pd.Timestamp('2016-01-25', tz='UTC')
    SIM_PARAMS_END = pd.Timestamp('2016-01-27', tz='UTC')
    SIM_PARAMS_DATA_FREQUENCY = 'minute'
    TRADING_CALENDAR_STRS = ('us_futures',)
    TRADING_CALENDAR_PRIMARY_CAL = 'us_futures'

    @classmethod
    def make_root_symbols_info(self):
        return pd.DataFrame({
            'root_symbol': ['FO'],
            'root_symbol_id': [1],
            'exchange': ['CME']})

    @classmethod
    def make_futures_info(self):
        return DataFrame({
            'symbol': ['FOF16', 'FOG16', 'FOH16', 'FOJ16', 'FOF22'],
            'root_symbol': ['FO', 'FO', 'FO', 'FO', 'FO'],
            'asset_name': ['Foo'] * 5,
            'start_date': [Timestamp('2015-01-05', tz='UTC'),
                           Timestamp('2015-02-05', tz='UTC'),
                           Timestamp('2015-03-05', tz='UTC'),
                           Timestamp('2015-04-05', tz='UTC'),
                           Timestamp('2021-01-05', tz='UTC')],
            'end_date': [Timestamp('2016-08-19', tz='UTC'),
                         Timestamp('2016-09-19', tz='UTC'),
                         Timestamp('2016-10-19', tz='UTC'),
                         Timestamp('2016-11-19', tz='UTC'),
                         Timestamp('2022-08-19', tz='UTC')],
            'notice_date': [Timestamp('2016-01-26', tz='UTC'),
                            Timestamp('2016-02-26', tz='UTC'),
                            Timestamp('2016-03-26', tz='UTC'),
                            Timestamp('2016-04-26', tz='UTC'),
                            Timestamp('2022-01-26', tz='UTC')],
            'expiration_date': [Timestamp('2016-01-26', tz='UTC'),
                                Timestamp('2016-02-26', tz='UTC'),
                                Timestamp('2016-03-26', tz='UTC'),
                                Timestamp('2016-04-26', tz='UTC'),
                                Timestamp('2022-01-26', tz='UTC')],
            'auto_close_date': [Timestamp('2016-01-26', tz='UTC'),
                                Timestamp('2016-02-26', tz='UTC'),
                                Timestamp('2016-03-26', tz='UTC'),
                                Timestamp('2016-04-26', tz='UTC'),
                                Timestamp('2022-01-26', tz='UTC')],
            'tick_size': [0.001] * 5,
            'multiplier': [1000.0] * 5,
            'exchange': ['CME'] * 5,
        })

    def test_create_continuous_future(self):
        cf_primary = self.asset_finder.create_continuous_future(
            'FO', 0, 'calendar')

        self.assertEqual(cf_primary.root_symbol, 'FO')
        self.assertEqual(cf_primary.offset, 0)
        self.assertEqual(cf_primary.roll_style, 'calendar')

        retrieved_primary = self.asset_finder.retrieve_asset(
            cf_primary.sid)

        self.assertEqual(retrieved_primary, cf_primary)

        cf_secondary = self.asset_finder.create_continuous_future(
            'FO', 1, 'calendar')

        self.assertEqual(cf_secondary.root_symbol, 'FO')
        self.assertEqual(cf_secondary.offset, 1)
        self.assertEqual(cf_secondary.roll_style, 'calendar')

        retrieved = self.asset_finder.retrieve_asset(
            cf_secondary.sid)

        self.assertEqual(retrieved, cf_secondary)

        self.assertNotEqual(cf_primary, cf_secondary)

    def test_current_contract(self):
        cf_primary = self.asset_finder.create_continuous_future(
            'FO', 0, 'calendar')
        bar_data = self.create_bardata(
            lambda: pd.Timestamp('2016-01-25', tz='UTC'))
        contract = bar_data.current(cf_primary, 'contract')

        self.assertEqual(contract.symbol, 'FOF16')

        bar_data = self.create_bardata(
            lambda: pd.Timestamp('2016-01-26', tz='UTC'))
        contract = bar_data.current(cf_primary, 'contract')

        self.assertEqual(contract.symbol, 'FOG16',
                         'Auto close at beginning of session so FOG16 is now '
                         'the current contract.')

        bar_data = self.create_bardata(
            lambda: pd.Timestamp('2016-01-27', tz='UTC'))
        contract = bar_data.current(cf_primary, 'contract')
        self.assertEqual(contract.symbol, 'FOG16')

    def test_current_contract_in_algo(self):
        code = dedent("""
from zipline.api import (
    record,
    continuous_future,
    schedule_function,
    get_datetime,
)

def initialize(algo):
    algo.primary_cl = continuous_future('FO', 0, 'calendar')
    algo.secondary_cl = continuous_future('FO', 1, 'calendar')
    schedule_function(record_current_contract)

def record_current_contract(algo, data):
    record(datetime=get_datetime())
    record(primary=data.current(algo.primary_cl, 'contract'))
    record(secondary=data.current(algo.secondary_cl, 'contract'))
""")
        algo = TradingAlgorithm(script=code,
                                sim_params=self.sim_params,
                                trading_calendar=self.trading_calendar,
                                env=self.env)
        results = algo.run(self.data_portal)
        result = results.iloc[0]

        self.assertEqual(result.primary.symbol,
                         'FOF16',
                         'Primary should be FOF16 on first session.')
        self.assertEqual(result.secondary.symbol,
                         'FOG16',
                         'Secondary should be FOG16 on first session.')

        result = results.iloc[1]
        # Second day, primary should switch to FOG
        self.assertEqual(result.primary.symbol,
                         'FOG16',
                         'Primary should be FOG16 on second session, auto '
                         'close is at beginning of the session.')
        self.assertEqual(result.secondary.symbol,
                         'FOH16',
                         'Secondary should be FOH16 on second session, auto '
                         'close is at beginning of the session.')

        result = results.iloc[2]
        # Second day, primary should switch to FOG
        self.assertEqual(result.primary.symbol,
                         'FOG16',
                         'Primary should remain as FOG16 on third session.')
        self.assertEqual(result.secondary.symbol,
                         'FOH16',
                         'Secondary should remain as FOH16 on third session.')

    def test_current_chain_in_algo(self):
        code = dedent("""
from zipline.api import (
    record,
    continuous_future,
    schedule_function,
    get_datetime,
)

def initialize(algo):
    algo.primary_cl = continuous_future('FO', 0, 'calendar')
    algo.secondary_cl = continuous_future('FO', 1, 'calendar')
    schedule_function(record_current_contract)

def record_current_contract(algo, data):
    record(datetime=get_datetime())
    primary_chain = data.current_chain(algo.primary_cl)
    secondary_chain = data.current_chain(algo.secondary_cl)
    record(primary_len=len(primary_chain))
    record(primary_first=primary_chain[0].symbol)
    record(primary_last=primary_chain[-1].symbol)
    record(secondary_len=len(secondary_chain))
    record(secondary_first=secondary_chain[0].symbol)
    record(secondary_last=secondary_chain[-1].symbol)
""")
        algo = TradingAlgorithm(script=code,
                                sim_params=self.sim_params,
                                trading_calendar=self.trading_calendar,
                                env=self.env)
        results = algo.run(self.data_portal)
        result = results.iloc[0]

        self.assertEqual(result.primary_len,
                         4,
                         'There should be only 4 contracts in the chain for '
                         'the primary, there are 5 contracts defined in the '
                         'fixture, but one has a start after the simulation '
                         'date.')
        self.assertEqual(result.secondary_len,
                         3,
                         'There should be only 3 contracts in the chain for '
                         'the primary, there are 5 contracts defined in the '
                         'fixture, but one has a start after the simulation '
                         'date. And the first is not included because it is '
                         'the primary on that date.')

        self.assertEqual(result.primary_first,
                         'FOF16',
                         'Front of primary chain should be FOF16 on first '
                         'session.')
        self.assertEqual(result.secondary_first,
                         'FOG16',
                         'Front of secondary chain should be FOG16 on first '
                         'session.')

        self.assertEqual(result.primary_last,
                         'FOJ16',
                         'End of primary chain should be FOJ16 on first '
                         'session.')
        self.assertEqual(result.secondary_last,
                         'FOJ16',
                         'End of secondary chain should be FOJ16 on first '
                         'session.')

        # Second day, primary should switch to FOG
        result = results.iloc[1]

        self.assertEqual(result.primary_len,
                         3,
                         'There should be only 3 contracts in the chain for '
                         'the primary, there are 5 contracts defined in the '
                         'fixture, but one has a start after the simulation '
                         'date. The first is not included because of roll.')
        self.assertEqual(result.secondary_len,
                         2,
                         'There should be only 2 contracts in the chain for '
                         'the primary, there are 5 contracts defined in the '
                         'fixture, but one has a start after the simulation '
                         'date. The first is not included because of roll, '
                         'the second is the primary on that date.')

        self.assertEqual(result.primary_first,
                         'FOG16',
                         'Front of primary chain should be FOG16 on second '
                         'session.')
        self.assertEqual(result.secondary_first,
                         'FOH16',
                         'Front of secondary chain should be FOH16 on second '
                         'session.')

        # These values remain FOJ16 because fixture data is not exhaustive
        # enough to move the end of the chain.
        self.assertEqual(result.primary_last,
                         'FOJ16',
                         'End of primary chain should be FOJ16 on second '
                         'session.')
        self.assertEqual(result.secondary_last,
                         'FOJ16',
                         'End of secondary chain should be FOJ16 on second '
                         'session.')
