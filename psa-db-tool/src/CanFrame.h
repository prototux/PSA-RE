#pragma once

#include <string>
#include "CanSignal.h"
#include "LanguageField.h"

using namespace std;

class CanFrame
{
public:
    CanFrame() {}
    ~CanFrame() {}

    uint16_t    getHexId()        const { return hexId_; }
    string      getName()         const { return name_; }
    void        printAltNames()   const;
    uint16_t    getLength()       const { return length_; }
    string      getComment(const char *lang) const;
    string      getType()         const { return type_; }
    string      getPeriod()       const { return period_; }

    void        print()           const;
    void        printSenders()    const;
    void        printReceivers()  const;

    void    setHexId(uint16_t hexId)      { hexId_ = hexId; }
    // void    setHexId(string hexId)        { hexId_ = stoi(hexId, nullptr, 16); }
    void    setName(string name)          { name_ = name; }
    void    addAltName(string name)       { altNames_.push_back(name); }
    void    setLength(uint16_t length)    { length_ = length; }
    void    addComment(LanguageField comment)    { comments_.push_back(comment); }
    void    setType(string type)          { type_ = type; }
    void    setPeriod(string period)      { period_ = period; }
    void    addSender(string sender)      { senders_.push_back(sender); }
    void    addReceiver(string receiver)  { receivers_.push_back(receiver); }
    void    addSignal(CanSignal signal)   { signals_.push_back(signal); }

    bool    isFrameInvalid()    const;

private:
    uint16_t        hexId_ = 0xFFFF;
    string          name_;
    vector<string>  altNames_;
    uint16_t        length_ = 0xFFFF;
    vector<LanguageField>  comments_;      // SHOULD BE PAIR
    string          type_;
    string          period_;
    vector<string>  senders_;
    vector<string>  receivers_;
    vector<CanSignal>   signals_;

    void printVector(vector<string> someVector) const;
};
