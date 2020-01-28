import alpaca_trade_api as tradeapi
import time
import datetime
import threading
from config import *

APCA_API_BASE_URL = "https://paper-api.alpaca.markets"


class LongShort:
    def __init__(self):
        self.alpaca = tradeapi.REST(API_KEY, SECRET_KEY, APCA_API_BASE_URL, 'v2')

        self.time_to_close = None
        self.time_since_open = None
        self.stock_universe = []
        self.owned_stocks = []
        self.positions = self.alpaca.list_positions()

        stock_symbols = ['DOMO', 'TLRY', 'SQ', 'MRO', 'AAPL', 'GM', 'SNAP', 'SHOP', 'SPLK', 'BA',
                         'AMZN', 'SUI', 'SUN', 'TSLA', 'CGC', 'SPWR', 'NIO', 'CAT', 'MSFT', 'PANW',
                         'OKTA', 'TWTR', 'TM', 'RTN', 'ATVI', 'GS', 'BAC', 'MS', 'TWLO', 'QCOM',
                         'GE', 'CHK', 'F', 'WFC', 'KO', 'VZ', 'DIS']

        for stock in stock_symbols:
            self.stock_universe.append([stock, 0, 0, 0, 0, 0])

    def run(self):
        orders = self.alpaca.list_orders(status="open")
        print("Current positions:")
        for i in range(len(self.positions)):
            self.owned_stocks.append(self.positions[i].__getattr__("symbol"))
            print(self.positions[i].__getattr__("symbol"), " ")
        print()
        print("Owned stocks:", self.owned_stocks)
        print("Current orders:")
        for i in range(len(orders)):
            print(orders[i].__getattr__("symbol"), " ")
        print()
        '''for order in orders:
            self.alpaca.cancel_order(order.id)'''

        print("Awaiting market open...")

        self.set_percent_changes_buy()
        self.update_curr_stock_prices()

        for stock in self.stock_universe:
            print(stock)

        set_percent_changes = threading.Thread(target=self.set_percent_changes_buy)
        set_percent_changes.start()
        set_percent_changes.join()

        update_curr_prices = threading.Thread(target=self.update_curr_stock_prices)
        update_curr_prices.start()
        update_curr_prices.join()

        self.auto_buy_order()

        await_open = threading.Thread(target=self.await_market_open)
        await_open.start()
        await_open.join()
        print("Market has opened!")

        while True:

            # Determine when the market will close so we can prepare to sell beforehand
            clock = self.alpaca.get_clock()
            opening_time = clock.next_open.replace(tzinfo=datetime.timezone.utc).timestamp()
            closing_time = clock.next_close.replace(tzinfo=datetime.timezone.utc).timestamp()
            curr_time = clock.timestamp.replace(tzinfo=datetime.timezone.utc).timestamp()
            self.time_to_close = closing_time - curr_time
            self.time_since_open = curr_time - opening_time

            if self.time_since_open == (60 * 15):
                while (self.time_since_open < (60 * 60)):
                    self.opening_auto_buy_order()

            if self.time_to_close < (60 * 15):
                # Close all positions when 15 minutes til market close
                print("Market closing soon.  Closing positions.")
                for position in self.positions:
                    if position.side == 'long':
                        orderSide = 'sell'
                    else:
                        orderSide = 'buy'
                    qty = abs(int(float(position.qty)))
                    respSO = []
                    tSubmitOrder = threading.Thread(target=self.place_order(qty, position.symbol, orderSide, respSO))
                    tSubmitOrder.start()
                    tSubmitOrder.join()

                # Run script again after market close for next trading day
                print("Sleeping until market close (15 minutes).")
                time.sleep(60 * 15)
            '''else:
                # Rebalance the portfolio
                t_rebalance = threading.Thread(target=self.rebalance)
                t_rebalance.start()
                t_rebalance.join()
                time.sleep(60)'''

    def auto_sell_order(self):
        while True:
            for stock in self.stock_universe:
                if stock[0] in self.owned_stocks:
                    self.alpaca.submit_order(stock[0], stock[5], 'sell', 'market', 'day')
                    self.owned_stocks.remove(stock[0])
                    print("Order for sell", stock[0], "for", stock[5], "shares placed!")

    def opening_auto_buy_order(self):
        for stock in self.stock_universe:
            if (self.get_percent_change(stock[0]) >= .03):
                bars = self.alpaca.get_barset(stock[0], 'minute', limit=1)
                if (bars[stock[0]][0].c > 300):
                    qty = 20
                elif (bars[stock[0]][0].c < 300 and bars[stock[0]][0].c > 100):
                    qty = 40
                elif (bars[stock[0]][0].c < 100 and bars[stock[0]][0].c > 10):
                    qty = 60
                else:
                    qty = 1000
                self.alpaca.submit_order(stock[0], qty, 'buy', 'market', 'day')
                for i, stock in enumerate(self.stock_universe):
                    if (self.stock_universe[i][0] == stock[0]):
                        self.stock_universe[i][5] = self.positions[i].__getattr__("qty")
            print(self.positions[i].__getattr__("symbol"), " ")
            print("Order for", stock[0], "for", qty, "shares placed!")

    def auto_buy_order(self):
        while True:
            for stock in self.stock_universe:
                bars = self.alpaca.get_barset(stock[0], 'minute', limit=1)
                if (bars[stock[0]][0].c > 300):
                    qty = 20
                elif (bars[stock[0]][0].c < 300 and bars[stock[0]][0].c > 100):
                    qty = 40
                elif (bars[stock[0]][0].c < 100 and bars[stock[0]][0].c > 10):
                    qty = 60
                else:
                    qty = 1000
                if self.get_percent_change(stock[0]) >= .003:
                    try:
                        print("Quantity of stock:", qty)
                        self.alpaca.submit_order(stock[0], qty, 'buy', 'market', 'day')
                        for i, stock in enumerate(self.stock_universe):
                            if self.stock_universe[i][0] == stock[0]:
                                self.stock_universe[i][2] = bars[stock[0][0].c]
                                self.stock_universe[i][5] = self.positions[i].__getattr__("qty")
                        print("Order for", stock[0], "for", qty, "shares placed!")
                    except:
                        print("Order <", qty, " ", stock[0], " buy", "> did not go through.")

    def place_order(self, symbol, qty, side, type, time_in_force):
        if qty > 0:
            if self.get_percent_change(symbol) >= .003:
                try:
                    self.alpaca.submit_order(symbol, qty, side, type, time_in_force)
                    print("Order placed!")
                except:
                    print("Order <", qty, " ", symbol, " ", side, "> did not go through.")
        else:
            print("Cannot place order for quantity 0 of <", symbol, " ", side, "> ")

    def get_percent_change(self, symbol):
        length = 2
        for i, stock in enumerate(self.stock_universe):
            if self.stock_universe[i][0] == symbol:
                bars = self.alpaca.get_barset(stock[0], 'day', limit=length)
                self.stock_universe[i][1] = (bars[stock[0]][len(bars[stock[0]]) - 1].c - bars[stock[0]][0].o) / bars[stock[0]][0].o
                #change = (bars[stock[0]][len(bars[stock[0]]) - 1].c - bars[stock[0]][0].o) / bars[stock[0]][0].o
                return self.stock_universe[i][1]

    def set_percent_changes_buy(self):
        length = 10
        for i, stock in enumerate(self.stock_universe):
            bars = self.alpaca.get_barset(stock[0], 'day', limit=length)
            self.stock_universe[i][1] = (bars[stock[0]][len(bars[stock[0]]) - 1].c - bars[stock[0]][0].o) / bars[stock[0]][0].o
        return self.stock_universe

    def get_percent_changes_sell(self):
        pass

    def await_market_open(self):
        is_open = self.alpaca.get_clock().is_open
        while not is_open:
            clock = self.alpaca.get_clock()
            opening_time = clock.next_open.replace(tzinfo=datetime.timezone.utc).timestamp()
            curr_time = clock.timestamp.replace(tzinfo=datetime.timezone.utc).timestamp()
            time_to_open = int((opening_time - curr_time) / 60)
            print(str(time_to_open) + " minutes til market open.")
            time.sleep(60)
            is_open = self.alpaca.get_clock().is_open

    def update_curr_stock_prices(self):
        while True:
            for i, stock in enumerate(self.stock_universe):
                bars = self.alpaca.get_barset(stock[0], 'minute', limit=1)
                self.stock_universe[i][3] = bars[stock[0]][0].c
            return self.stock_universe
