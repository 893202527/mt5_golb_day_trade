//+------------------------------------------------------------------+
//| GoldenBot.mq5 - XAUUSD AI Trading EA                              |
//+------------------------------------------------------------------+
#property copyright "Trading System"
#property version   "1.00"
#property description "AI-driven XAUUSD trading bot with ZeroMQ bridge"

#include <ZmqChannel.mqh>
#include <OrderManager.mqh>

input double RiskPercent = 1.0;
input int    InpMagic    = 20260528;

CZmqChannel   g_zmq;
COrderManager g_order(Symbol(), InpMagic);

int OnInit()
{
    if(!g_zmq.Start())
    {
        Print("ZeroMQ init failed");
        return INIT_FAILED;
    }
    Print("GoldenBot started on ", Symbol());
    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
    Print("GoldenBot stopped");
}

void OnTick()
{
    static datetime lastM5 = 0, lastH1 = 0, lastH4 = 0;

    datetime curM5 = iTime(Symbol(), PERIOD_M5, 0);
    if(curM5 != lastM5 && lastM5 != 0)
        OnBarClose(PERIOD_M5);
    lastM5 = curM5;

    datetime curH1 = iTime(Symbol(), PERIOD_H1, 0);
    if(curH1 != lastH1 && lastH1 != 0)
        OnBarClose(PERIOD_H1);
    lastH1 = curH1;

    datetime curH4 = iTime(Symbol(), PERIOD_H4, 0);
    if(curH4 != lastH4 && lastH4 != 0)
        OnBarClose(PERIOD_H4);
    lastH4 = curH4;
}

string TfToString(ENUM_TIMEFRAMES tf)
{
    switch(tf)
    {
        case PERIOD_M5:  return "M5";
        case PERIOD_H1:  return "H1";
        case PERIOD_H4:  return "H4";
        default:         return "M5";
    }
}

void PublishBar(ENUM_TIMEFRAMES tf, string tfStr)
{
    double open  = iOpen(Symbol(), tf, 1);
    double high  = iHigh(Symbol(), tf, 1);
    double low   = iLow(Symbol(), tf, 1);
    double close = iClose(Symbol(), tf, 1);
    long   vol   = iVolume(Symbol(), tf, 1);
    int    spread = (int)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);
    datetime barTime = iTime(Symbol(), tf, 1);

    g_zmq.PublishOHLC(Symbol(), tfStr, barTime, open, high, low, close, vol, spread);
}

void OnBarClose(ENUM_TIMEFRAMES tf)
{
    PublishBar(tf, TfToString(tf));

    if(tf == PERIOD_M5 && !g_order.HasOpenPosition())
    {
        string action, reason;
        double confidence, entry, sl, tp;

        if(g_zmq.QuerySignal(action, confidence, entry, sl, tp, reason))
        {
            ProcessSignal(action, confidence, entry, sl, tp, reason);
        }
    }
}

void ProcessSignal(string action, double confidence, double entry, double sl, double tp, string reason)
{
    double lots = g_order.GetLots(RiskPercent, MathAbs(entry - sl) / SymbolInfoDouble(Symbol(), SYMBOL_POINT));

    ulong ticket = 0;
    if(action == "buy")
        ticket = g_order.OpenBuy(lots, sl, tp, reason);
    else if(action == "sell")
        ticket = g_order.OpenSell(lots, sl, tp, reason);

    if(ticket > 0)
        Print("Trade opened: ", action, " ticket=", ticket, " lots=", lots, " reason=", reason);
    else
        Print("Trade failed: ", action, " error=", GetLastError());
}
