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
import threading

class Algo(QCAlgorithm):

    SYMBOL = "EURUSD"
    RESOL = Resolution.Minute
    
    TREND_PERIODS = 200
    
    TP_PERCENTAGE = decimal.Decimal(1.01)
    SL_PERCENTAGE = decimal.Decimal(1.008)

    associatedOrders = {}
    associatedOrdersLock = threading.Lock()

    def Initialize(self):

        self.SetStartDate(2011, 1, 1)
        self.SetEndDate(2018, 1, 1)
        self.SetCash(5000)

        self.forexPair = self.AddForex(self.SYMBOL, self.RESOL)
        self.SetBrokerageModel(BrokerageName.FxcmBrokerage)

        self.fast = self.SMA(self.forexPair.Symbol, 50, self.forexPair.Resolution)
        self.slow = self.SMA(self.forexPair.Symbol, 200, self.forexPair.Resolution)
        self.SMATrend = 0
        
        self.stoch = self.STO(self.forexPair.Symbol, 14, 14, 3, self.forexPair.Resolution)
        
        self.previousIsOverbought = None
        self.previousIsOversold = None

        self.previousTime = self.Time

    def OnData(self, data):
        
        if not self.slow.IsReady or not self.fast.IsReady or not self.stoch.IsReady:
            return
        
        # only once per period
        if self.previousTime.time().minute == self.Time.time().minute:
            return

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

        holdings = self.Portfolio[self.forexPair.Symbol].Quantity
        price = data[self.forexPair.Symbol].Close

        # uptrend for a certain amount of time
        if self.SMATrend >= self.TREND_PERIODS:
            # if it is not oversold
            if self.stoch.StochD.Current.Value > 20:
                # if it just recently stopped being oversold
                if self.previousIsOversold is not None and self.previousIsOversold == True:
                    
                    # buy
                    self.MarketOrder(self.forexPair.Symbol, 1000)
                    
                    self.associatedOrdersLock.acquire()
                    
                    # set up take profit and stop loss orders
                    takeProfitOrderTicket = self.LimitOrder(self.forexPair.Symbol, -1000, price * self.TP_PERCENTAGE)
                    stopLossOrderTicket = self.StopMarketOrder(self.forexPair.Symbol, -1000, price / self.SL_PERCENTAGE)
                    
                    # associate them with one another
                    self.associatedOrders[takeProfitOrderTicket.OrderId] = stopLossOrderTicket
                    self.associatedOrders[stopLossOrderTicket.OrderId] = takeProfitOrderTicket

                    self.associatedOrdersLock.release()
                    
        if self.stoch.StochD.Current.Value <= 20:
            self.previousIsOversold = True
        else:
            self.previousIsOversold = False




        # downtrend for a certain amount of time
        if self.SMATrend <= -(self.TREND_PERIODS):
            # if it is not overbought
            if self.stoch.StochD.Current.Value < 80:
                # if it just recently stopped being overbought
                if self.previousIsOverbought is not None and self.previousIsOverbought == True:
                    
                    # sell
                    self.MarketOrder(self.forexPair.Symbol, -1000)
                    
                    self.associatedOrdersLock.acquire()
                    
                    # set up take profit and stop loss orders
                    takeProfitOrderTicket = self.LimitOrder(self.forexPair.Symbol, 1000, price / self.TP_PERCENTAGE)
                    stopLossOrderTicket = self.StopMarketOrder(self.forexPair.Symbol, 1000, price * self.SL_PERCENTAGE)
                    
                    # associate them with one another
                    self.associatedOrders[takeProfitOrderTicket.OrderId] = stopLossOrderTicket
                    self.associatedOrders[stopLossOrderTicket.OrderId] = takeProfitOrderTicket

                    self.associatedOrdersLock.release()

        if self.stoch.StochD.Current.Value >= 80:
            self.previousIsOverbought = True
        else:
            self.previousIsOverbought = False
            
        self.previousTime = self.Time


    def OnOrderEvent(self, orderEvent):
        
        if orderEvent.Status == OrderStatus.Filled:
            
            order = self.Transactions.GetOrderById(orderEvent.OrderId)
            
            if order.Type == OrderType.Limit or order.Type == OrderType.StopMarket:

                self.associatedOrdersLock.acquire()                
                associatedOrder = self.associatedOrders[order.Id]
                associatedOrder.Cancel()

                del self.associatedOrders[order.Id]
                del self.associatedOrders[associatedOrder.OrderId]
                self.associatedOrdersLock.release()
            # if order.Type == OrderType.Limit or order.Type == OrderType.StopMarket:
            #     self.Transactions.CancelOpenOrders(order.Symbol)
















