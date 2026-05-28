//+------------------------------------------------------------------+
//| ZmqChannel.mqh - ZeroMQ wrapper for MT5 EA                        |
//+------------------------------------------------------------------+
#property copyright "Trading System"

#ifndef ZMQ_CHANNEL_MQH
#define ZMQ_CHANNEL_MQH

#include <Zmq/Zmq.mqh>

class CZmqChannel
{
private:
    Context m_ctx;
    Socket  m_pub;
    Socket  m_req;

    string  m_pubEndpoint;
    string  m_reqEndpoint;

public:
    CZmqChannel()
    {
        m_pubEndpoint = "tcp://127.0.0.1:5555";
        m_reqEndpoint = "tcp://127.0.0.1:5556";
    }

    ~CZmqChannel()
    {
        m_pub.close();
        m_req.close();
        m_ctx.destroy();
    }

    bool Start()
    {
        m_ctx.create();
        if(!m_ctx.isValid()) return false;

        m_pub = m_ctx.createSocket(ZMQ_PUB);
        if(!m_pub.isValid()) return false;

        m_req = m_ctx.createSocket(ZMQ_REQ);
        if(!m_req.isValid()) return false;

        if(!m_pub.bind(m_pubEndpoint)) return false;
        if(!m_req.connect(m_reqEndpoint)) return false;

        return true;
    }

    void PublishOHLC(string symbol, string tf, datetime barTime,
                     double open, double high, double low, double close,
                     long tickVolume, int spread)
    {
        string json = StringFormat(
            "OHLC {\"type\":\"ohlc\",\"symbol\":\"%s\",\"tf\":\"%s\",\"time\":\"%s\","
            "\"open\":%.2f,\"high\":%.2f,\"low\":%.2f,\"close\":%.2f,"
            "\"tick_volume\":%d,\"spread\":%d}",
            symbol, tf, TimeToString(barTime, TIME_DATE|TIME_SECONDS),
            open, high, low, close, tickVolume, spread
        );
        ZmqMsg msg(json);
        m_pub.send(msg, false);
    }

    bool QuerySignal(string &action, double &confidence,
                     double &entryPrice, double &sl, double &tp, string &reason)
    {
        string req = "{\"type\":\"query\",\"symbol\":\"XAUUSD\",\"tf\":\"M5\"}";
        ZmqMsg reqMsg(req);
        m_req.send(reqMsg);

        ZmqMsg repMsg;
        int rc = m_req.recv(repMsg, 3000);
        if(rc < 0) return false;

        string rep;
        repMsg.getString(rep);
        // Parse JSON response (simplified; in production use a JSON parser)
        action = ParseJsonString(rep, "action");
        confidence = ParseJsonDouble(rep, "confidence");
        entryPrice = ParseJsonDouble(rep, "entry_price");
        sl = ParseJsonDouble(rep, "sl");
        tp = ParseJsonDouble(rep, "tp");
        reason = ParseJsonString(rep, "reason");
        return true;
    }

private:
    string ParseJsonString(string json, string key)
    {
        string search = "\"" + key + "\":\"";
        int start = StringFind(json, search);
        if(start < 0) return "";
        start += StringLen(search);
        int end = StringFind(json, "\"", start);
        if(end < 0) return "";
        return StringSubstr(json, start, end - start);
    }

    double ParseJsonDouble(string json, string key)
    {
        string search = "\"" + key + "\":";
        int start = StringFind(json, search);
        if(start < 0) return 0.0;
        start += StringLen(search);
        int end = StringFind(json, ",", start);
        if(end < 0) end = StringFind(json, "}", start);
        if(end < 0) return 0.0;
        string val = StringSubstr(json, start, end - start);
        StringReplace(val, " ", "");
        return StringToDouble(val);
    }
};

#endif
