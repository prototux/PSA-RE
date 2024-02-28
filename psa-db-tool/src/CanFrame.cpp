#include "CanFrame.h"
#include <iostream>
#include <iomanip>

void CanFrame::printAltNames() const
{
    printVector(altNames_);
}

std::string CanFrame::getComment(const char *lang) const
{
    for (size_t i=0; i<comments_.size(); i++)
    {
        if (comments_[i].isLanguageEqual(lang))
            return comments_[i].getText();
    }
    return "";
}

void CanFrame::printSenders() const
{
    printVector(senders_);
}

void CanFrame::printReceivers() const
{
    printVector(receivers_);
}

bool CanFrame::isFrameInvalid() const
{
    std::string missingPart{""};
    if (hexId_ == 0xFFFF)
        missingPart.assign("ID");
    else if (name_ == "")
        missingPart.assign("NAME");
    else if (length_ == 0xFFFF)
        missingPart.assign("DATA_LENGTH");
    else
        return EXIT_SUCCESS;
    
    std::cout << "Frame doesn't have " << missingPart << " field. Invalid frame." << std::endl;
    return EXIT_FAILURE;
}

void CanFrame::printVector(std::vector<std::string> someVector) const
{
    for (std::string unitInVector : someVector)
    {
        std::cout << "\'" << unitInVector << "\' ";
    }
    std::cout << std::endl;
}

void CanFrame::print() const
{
    std::cout << "CAN_ID: 0x" << std::hex << hexId_;
    std::cout << " (" << std::dec << hexId_ << ")   ";
    std::cout << "NAME: " << name_ << std::endl;
    std::cout << "ALTERNATIVE NAMES: ";
    printAltNames();
    std::cout << "COMMENT: " << getComment("en") << std::endl;
    std::cout << "TYPE: " << type_ << "     ";
    std::cout << "LENGTH: " << length_ << "     ";
    std::cout << "PERIOD: " << period_ << std::endl;
    std::cout << "SENDERS: ";
    printSenders();
    std::cout << "RECEIVERS: ";
    printReceivers();
    std::cout << "SIGNALS:   _____NAME____BITS__TYPE__FACTOR__OFFSET____MIN____MAX___UNITS_COMMENT____VALUES------------" << std::endl;
    for (CanSignal signal : signals_)
        signal.print();
}
