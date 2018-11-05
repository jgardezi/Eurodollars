from clr import AddReference
import decimal
AddReference("System")
AddReference("QuantConnect.Algorithm")
AddReference("QuantConnect.Indicators")
AddReference("QuantConnect.Common")

from System import *
from QuantConnect import *
from QuantConnect.Algorithm import *
from QuantConnect.Indicators import *
from datetime import datetime

class Algo(QCAlgorithm):

    SYMBOL = "EURUSD"
    RESOL = Resolution.Hour
    TREND_PERIODS = 10

    def Initialize(self):

        self.SetStartDate(2017, 1, 1)
        self.SetEndDate(2018, 1, 1)
        self.SetCash(1000000)

        self.forexPair = self.AddForex(self.SYMBOL, self.RESOL)
        self.SetBrokerageModel(BrokerageName.FxcmBrokerage)

        self.slow = self.SMA(self.forexPair.Symbol, 50, self.forexPair.Resolution)
        self.fast = self.SMA(self.forexPair.Symbol, 200, self.forexPair.Resolution)
        self.SMATrend = 0
        
        self.stoch = self.STO(self.forexPair.Symbol, 21, 21, 7, self.forexPair.Resolution)
        
        self.previousIsOverbought = None
        self.previousIsOversold = None

        self.previousTime = self.Time

    def OnData(self, data):
        
        if not self.slow.IsReady or not self.fast.IsReady:
            return
        
        # if self.previousIsOverbought is None and self.previousIsOversold is None:
        #     return
        
        if self.previousTime.time().hour == self.Time.time().hour:
            return

        holdings = self.Portfolio[self.forexPair.Symbol].Quantity
        
        # uptrend
        if self.fast.Current.Value > self.slow.Current.Value:
            if self.SMATrend < 0:
                self.SMATrend = 0
            self.SMATrend += 1

        # downtrend
        elif self.fast.Current.Value < self.slow.Current.Value:
            if self.SMATrend > 0:
                self.SMATrend = 0
            self.SMATrend -= 1
            
    
        self.Debug("Holdings: " + str(holdings))

        # uptrend for a certain amount of time
        if holdings <= 0 and self.SMATrend >= self.TREND_PERIODS:

            price = data[self.forexPair.Symbol].Close
            tpPercentage = decimal.Decimal(1.02)
            slPercentage = decimal.Decimal(1.02)

            self.MarketOrder(self.forexPair.Symbol, 1000)
            self.LimitOrder(self.forexPair.Symbol, -1000, price * tpPercentage) # take profit
            self.StopMarketOrder(self.forexPair.Symbol, -1000, price / slPercentage) # stop loss

        # downtrend for a certain amount of time
        # elif self.SMATrend <= -self.TREND_PERIODS:
        #     self.MarketOrder(self.SYMBOL, -1000)
            
        self.previousTime = self.Time




    def OnOrderEvent(self, orderEvent):
        
        if orderEvent.Status == OrderStatus.Filled or orderEvent.Status == OrderStatus.PartiallyFilled:
            
            order = self.Transactions.GetOrderById(orderEvent.OrderId)

            if order.Type == OrderType.Limit or order.Type == OrderType.StopMarket:
                
                self.Transactions.CancelOpenOrders(order.Symbol)






