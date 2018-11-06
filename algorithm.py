from clr import AddReference


AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Indicators")
AddReference("QuantConnect.Common")


from System import *
from QuantConnect import *
from QuantConnect.Algorithm import *
from QuantConnect.Indicators import *
from datetime import datetime
import decimal
import threading
from enum import Enum, auto


class Position(Enum):
    """Enum defining either a long position or short position."""
    LONG = auto()
    SHORT = auto()


class EURUSDForexAlgo(QCAlgorithm):
    """QuantConnect Algorithm Class for trading the EURUSD forex pair."""

    # symbol of the forex pair: European Euros and US Dollars
    SYMBOL = "EURUSD"

    # hourly resolution for data and bot activity
    RESOL = Resolution.Hour

    # number of periods where the fast moving average is
    # above or below the slow moving average before
    # a trend is confirmed
    TREND_PERIODS = 17

    # limit for the number of trades per trend
    TREND_LIMIT_NUM_TRADES = 3

    # maximum holdings for each market direction
    MAX_HOLDING_ONE_DIRECTION = 0

    # units of currency for each trade
    TRADE_SIZE = 5000

    # take-proft and stop-loss offsets.
    TP_OFFSET = decimal.Decimal(0.0007)
    SL_OFFSET = decimal.Decimal(0.0017)

    # stochastic indicator levels for overbought and oversold
    STOCH_OVERBOUGHT_LEVEL = 80
    STOCH_OVERSOLD_LEVEL = 20
    
    # dictionary to keep track of associated take-profit and
    # stop-loss orders
    associatedOrders = {}

    # concurrency control for the dictionary
    associatedOrdersLock = threading.Lock()

    def Initialize(self):
        """Method called to initialize the trading algorithm."""

        # backtest testing range
        self.SetStartDate(2007, 1, 1)
        self.SetEndDate(2018, 11, 5)

        # amount of cash to use for backtest
        self.SetCash(10000)

        # forex pair object
        self.forexPair = self.AddForex(self.SYMBOL, self.RESOL)

        # brokerage model dictates the costs, slippage model, and fees
        # associated with the broker
        self.SetBrokerageModel(BrokerageName.FxcmBrokerage)

        # define a slow and fast moving average indicator
        # slow moving average indicator: 200 periods
        # fast moving average indicator: 50 periods
        # these indicator objects are automatically updated
        self.slow = self.SMA(self.forexPair.Symbol, 200, self.forexPair.Resolution)
        self.fast = self.SMA(self.forexPair.Symbol, 50, self.forexPair.Resolution)

        # counter defining the number of periods of the ongoing trend
        self.SMATrend = 0

        # number of trades executed in this trend
        self.trendNumTrades = 0

        # stochastic indicator
        # stochastic period: 9
        # stochastic k period: 9
        # stochastic d period: 5
        self.stoch = self.STO(self.forexPair.Symbol, 9, 9, 5, self.forexPair.Resolution)
        
        # keeps track of overbought/oversold conditions in the previous period
        self.previousIsOverbought = None
        self.previousIsOversold = None

        # keeps track of the time of the previous period
        self.previousTime = self.Time


    def OnData(self, data):
        """Method called when new data is ready for each period."""
        
        # only trade when the indicators are ready
        if not self.slow.IsReady or not self.fast.IsReady or not self.stoch.IsReady:
            return None
        
        # trade only once per period
        if self.previousTime.time().hour == self.Time.time().hour:
            return None

        self.periodPreUpdateStats()

        price = data[self.forexPair.Symbol].Close

        # if it is suitable to go long during this period
        if (self.entrySuitability() == Position.LONG):

            self.enterMarketOrderPosition(
                    symbol=self.forexPair.Symbol,
                    position=Position.LONG,
                    posSize=self.TRADE_SIZE,
                    tp=round(price + self.TP_OFFSET, 4),
                    sl=round(price - self.SL_OFFSET, 4))

        # it is suitable to go short during this period
        elif (self.entrySuitability() == Position.SHORT):
                        
            self.enterMarketOrderPosition(
                    symbol=self.forexPair.Symbol,
                    position=Position.SHORT,
                    posSize=self.TRADE_SIZE,
                    tp=round(price - self.TP_OFFSET, 4),
                    sl=round(price + self.SL_OFFSET, 4))

        self.periodPostUpdateStats()


    def entrySuitability(self):
        """Determines the suitability of entering a position for the current period.
        Returns either Position.LONG, Position.SHORT, or None"""

        # units of currency that the bot currently holds
        holdings = self.Portfolio[self.forexPair.Symbol].Quantity

        # conditions for going long (buying)
        if (
                # uptrend for a certain number of periods
                self.SMATrend >= self.TREND_PERIODS and
                # if it is not oversold
                self.stoch.StochD.Current.Value > self.STOCH_OVERSOLD_LEVEL and
                # if it just recently stopped being oversold
                self.previousIsOversold is not None and
                self.previousIsOversold == True and
                # if holdings does not exceed the limit for a direction
                holdings <= self.MAX_HOLDING_ONE_DIRECTION and
                # if number of trades during this trend does not exceed
                # the number of trades per trend
                self.trendNumTrades < self.TREND_LIMIT_NUM_TRADES
            ):
            
            return Position.LONG

        # conditions for going short (selling)
        elif (
                # downtrend for a certain number of periods
                self.SMATrend <= -(self.TREND_PERIODS) and
                # if it is not overbought
                self.stoch.StochD.Current.Value < self.STOCH_OVERBOUGHT_LEVEL and
                # if it just recently stopped being overbought
                self.previousIsOverbought is not None and
                self.previousIsOverbought == True and
                # if holdings does not exceed the limit for a direction
                holdings >= -self.MAX_HOLDING_ONE_DIRECTION and
                # if number of trades during this trend does not exceed
                # the number of trades per trend
                self.trendNumTrades < self.TREND_LIMIT_NUM_TRADES
            ):

            return Position.SHORT
            
        # unsuitable to enter a position for now
        return None


    def periodPreUpdateStats(self):
        """Method called before considering trades for each period."""

        # uptrend: if the fast moving average is above the slow moving average
        if self.fast.Current.Value > self.slow.Current.Value:

            if self.SMATrend < 0:

                self.SMATrend = 0
                self.trendNumTrades = 0

            self.SMATrend += 1

        # downtrend: if the fast moving average is below the slow moving average
        elif self.fast.Current.Value < self.slow.Current.Value:

            if self.SMATrend > 0:

                self.SMATrend = 0
                self.trendNumTrades = 0

            self.SMATrend -= 1


    def periodPostUpdateStats(self):
        """Method called after considering trades for each period."""

        if self.stoch.StochD.Current.Value <= self.STOCH_OVERSOLD_LEVEL:
            self.previousIsOversold = True
        else:
            self.previousIsOversold = False
            
        if self.stoch.StochD.Current.Value >= self.STOCH_OVERBOUGHT_LEVEL:
            self.previousIsOverbought = True
        else:
            self.previousIsOverbought = False

        self.previousTime = self.Time


    def enterMarketOrderPosition(self, symbol, position, posSize, tp, sl):
        """Enter a position (either Position.LONG or Position.Short)
        for the given symbol with the position size using a market order.
        Associated take-profit (tp) and stop-loss (sl) orders are entered."""

        self.associatedOrdersLock.acquire()

        if position == Position.LONG:

            self.Buy(symbol, posSize)

            takeProfitOrderTicket = self.LimitOrder(symbol, -posSize, tp)
            stopLossOrderTicket = self.StopMarketOrder(symbol, -posSize, sl)

        elif position == Position.SHORT:

            self.Sell(symbol, posSize)

            takeProfitOrderTicket = self.LimitOrder(symbol, posSize, tp)
            stopLossOrderTicket = self.StopMarketOrder(symbol, posSize, sl)

        # associate the take-profit and stop-loss orders with one another
        self.associatedOrders[takeProfitOrderTicket.OrderId] = stopLossOrderTicket
        self.associatedOrders[stopLossOrderTicket.OrderId] = takeProfitOrderTicket

        self.associatedOrdersLock.release()
        
        self.trendNumTrades += 1


    def OnOrderEvent(self, orderEvent):
        """Method called when an order has an event."""
        
        # if the event associated with the order is about an
        # order being fully filled
        if orderEvent.Status == OrderStatus.Filled:
            
            order = self.Transactions.GetOrderById(orderEvent.OrderId)
            
            # if the order is a take-profit or stop-loss order
            if order.Type == OrderType.Limit or order.Type == OrderType.StopMarket:

                self.associatedOrdersLock.acquire()
                
                # during volatile markets, the associated order and
                # this order may have been triggered in quick
                # succession, so this method is called twice
                # with this order and the associated order.
                # this prevents a runtime error in this case.
                if order.Id not in self.associatedOrders:
                    self.associatedOrdersLock.release()
                    return
                
                # obtain the associated order and cancel it.
                associatedOrder = self.associatedOrders[order.Id]
                associatedOrder.Cancel()

                # remove the entries of this order and its
                # associated order from the hash table.
                del self.associatedOrders[order.Id]
                del self.associatedOrders[associatedOrder.OrderId]
                
                self.associatedOrdersLock.release()
                

    def OnEndOfAlgorithm(self):
        """Method called when the algorithm terminates."""

        # liquidate all holdings (all unrealized profits/losses will be realized).
        # long and short positions are closed irrespective of profits/losses.
        self.Liquidate(self.forexPair.Symbol)
