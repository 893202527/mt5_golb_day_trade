//+------------------------------------------------------------------+
//| OrderManager.mqh - Trade execution wrapper                        |
//+------------------------------------------------------------------+
#property copyright "Trading System"

#ifndef ORDER_MANAGER_MQH
#define ORDER_MANAGER_MQH

#include <Trade/Trade.mqh>

class COrderManager
{
private:
    CTrade m_trade;
    string m_symbol;
    int    m_magic;

public:
    COrderManager(string symbol, int magic = 20260528)
    {
        m_symbol = symbol;
        m_magic = magic;
        m_trade.SetExpertMagicNumber(m_magic);
    }

    ulong OpenBuy(double volume, double sl, double tp, string comment = "")
    {
        m_trade.PositionOpen(m_symbol, ORDER_TYPE_BUY, volume,
                             SymbolInfoDouble(m_symbol, SYMBOL_ASK),
                             sl, tp, comment);
        return m_trade.ResultOrder();
    }

    ulong OpenSell(double volume, double sl, double tp, string comment = "")
    {
        m_trade.PositionOpen(m_symbol, ORDER_TYPE_SELL, volume,
                             SymbolInfoDouble(m_symbol, SYMBOL_BID),
                             sl, tp, comment);
        return m_trade.ResultOrder();
    }

    bool ClosePosition(ulong ticket)
    {
        return m_trade.PositionClose(ticket);
    }

    bool HasOpenPosition()
    {
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(PositionSelectByTicket(ticket) &&
               PositionGetInteger(POSITION_MAGIC) == m_magic &&
               PositionGetString(POSITION_SYMBOL) == m_symbol)
                return true;
        }
        return false;
    }

    double GetLots(double riskPercent, double slPips)
    {
        double balance = AccountInfoDouble(ACCOUNT_BALANCE);
        double riskMoney = balance * riskPercent / 100.0;
        double tickValue = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_VALUE);
        double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
        double slPrice = slPips * point * 10;
        if(slPrice <= 0) return 0.01;
        double lots = riskMoney / (slPrice * tickValue / point);
        double minLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MIN);
        double maxLot = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MAX);
        double step = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_STEP);
        lots = MathMax(minLot, MathMin(maxLot, lots));
        lots = MathFloor(lots / step) * step;
        return lots;
    }
};

#endif
