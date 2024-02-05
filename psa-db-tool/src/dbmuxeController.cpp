#include "dbmuxeController.h"
#include "ryml.hpp"
#include "ryml_std.hpp"

int parsePsaYaml(const char *yamlFile, CanFrame &thisFrame) {

    std::string yamlFileContent = get_file_contents(yamlFile);
    ryml::Tree tree = ryml::parse_in_place(ryml::to_substr(yamlFileContent));

    for (ryml::ConstNodeRef const& frameParam : tree.crootref())
    {
        if (frameParam.key() == "id")
        {
            std::uint16_t tempId;
            ryml::atox(frameParam.val(), &tempId);
            thisFrame.setHexId(tempId);
        }
        else if (frameParam.key() == "name")
        {
            std::string tempName {frameParam.val().str, frameParam.val().len};
            thisFrame.setName(tempName);
        }
        else if (frameParam.key() == "alt_names")
        {
            for (ryml::ConstNodeRef const& alternativeName : frameParam.children())
            {
                std::string tempAltName;
                alternativeName >> tempAltName;
                thisFrame.addAltName(tempAltName);
            }
        }
        else if (frameParam.key() == "length")
        {
            std::uint16_t tempLength;
            ryml::atou(frameParam.val(), &tempLength);
            thisFrame.setLength(tempLength);
            // std::cout << "PARAMETER LENGTH: " << frameParam.val().len << " " << std::endl;
        }
        else if (frameParam.key() == "comment")
        {
            for (ryml::ConstNodeRef const& comment : frameParam.children())
            {
                // std::string tempCommentLang {comment.key().str, comment.key().len};
                std::string tempCommentText {comment.val().str, comment.val().len};
                std::LanguageField tempComment(comment.key().begin(), tempCommentText);
                thisFrame.addComment(tempComment);
            }
        }
        else if (frameParam.key() == "type")
        {
            std::string tempType {frameParam.val().str, frameParam.val().len};
            thisFrame.setType(tempType);
        }
        else if (frameParam.key() == "periodicity")
        {
            std::string tempPeriod {frameParam.val().str, frameParam.val().len};
            thisFrame.setPeriod(tempPeriod);
        }
        else if (frameParam.key() == "senders")
        {
            for (ryml::ConstNodeRef const& sender : frameParam.children())
            {
                std::string tempSender;
                sender >> tempSender;
                thisFrame.addSender(tempSender);
            }
        }
        else if (frameParam.key() == "receivers")
        {
            for (ryml::ConstNodeRef const& receiver : frameParam.children())
            {
                std::string tempReceiver;
                receiver >> tempReceiver;
                thisFrame.addReceiver(tempReceiver);
            }
        }
        else if (frameParam.key() == "signals")
        {
            for (ryml::ConstNodeRef const& signal : frameParam.children())
            {
                CanSignal tempCanSignal;
                memset(&tempCanSignal, 0, sizeof(tempCanSignal));
                std::string tempName {signal.key().str, signal.key().len};
                tempCanSignal.setName(tempName);
                for (ryml::ConstNodeRef const& signalParam : signal.children())
                {
                    if (signalParam.key() == "bits")
                    {
                        std::string signalPositionStr {signalParam.val().str, signalParam.val().len};
                        parseSignalPosition(signalPositionStr, tempCanSignal);
                    }
                    else if (signalParam.key() == "type")
                    {
                        std::string tempType {signalParam.val().str, signalParam.val().len};
                        tempCanSignal.setType(tempType);
                    }
                    else if (signalParam.key() == "factor")
                    {
                        float tempFactor;
                        ryml::atof(signalParam.val(), &tempFactor);
                        tempCanSignal.setFactor(tempFactor);
                    }
                    else if (signalParam.key() == "offset")
                    {
                        std::int16_t tempOffset;
                        ryml::atoi(signalParam.val(), &tempOffset);
                        tempCanSignal.setOffset(tempOffset);
                    }
                    else if (signalParam.key() == "min")
                    {
                        std::int16_t tempMin;
                        ryml::atoi(signalParam.val(), &tempMin);
                        tempCanSignal.setMin(tempMin);
                    }
                    else if (signalParam.key() == "max")
                    {
                        std::int16_t tempMax;
                        ryml::atoi(signalParam.val(), &tempMax);
                        tempCanSignal.setMax(tempMax);
                    }
                    else if (signalParam.key() == "units")
                    {
                        std::string tempUnits {signalParam.val().str, signalParam.val().len};
                        tempCanSignal.setUnits(tempUnits);
                    }
                    else if (signalParam.key() == "values")
                    {
                        for (ryml::ConstNodeRef const& value : signalParam.children())
                        {
                            vector<std::LanguageField> tempSignalValueMeanings;
                            for (ryml::ConstNodeRef const &valueMeaning : value.children())
                            {
                                std::string tempMeaningDescription(valueMeaning.val().str, valueMeaning.val().len);
                                std::LanguageField tempLangField(valueMeaning.key().begin(), tempMeaningDescription);
                                tempSignalValueMeanings.push_back(tempLangField);
                            }
                            int16_t tempValue;
                            ryml::atox(value.key(), &tempValue);
                            tempCanSignal.addValueMeaning(tempValue, tempSignalValueMeanings);
                        }
                    }
                    else
                    {
                        std::cout << "Unknown signal parameter [" << signalParam.key() << "].\n";
                    }
                }
                thisFrame.addSignal(tempCanSignal);
            }
        }
        else
        {
            std::cout << "Unknown CAN message parameter [" << frameParam.key() << "].\n";
        }
    }
/*
    for (size_t msgParamId = tree.first_child(tree.root_id()); msgParamId != ryml::NONE;
                msgParamId = tree.next_sibling(msgParamId)) {
        std::cout << "MsgParamId = " << msgParamId << " \n";
        if (tree.key(msgParamId) == "type") {
            tree["type"] >> thisFrame.type;
        } else if (tree.key(msgParamId) == "periodicity") {
            tree["periodicity"] >> thisFrame.periodicity;
        } else if (tree.key(msgParamId) == "senders") {
            ryml::NodeRef senders = tree["senders"];
            for (ryml::NodeRef const &child : senders.children()) {
                std::string sender;
                child >> sender;
                thisFrame.senders.push_back(sender);
            }
        } else if (tree.key(msgParamId) == "signals") {
            has_signals = true;
            ryml::NodeRef signals = tree["signals"];
            for (ryml::NodeRef const &signal : signals.children()) {
                CanSignal tempCanSignal;
                tempCanSignal.scale = 1;
                tempCanSignal.offset = 0;
                tempCanSignal.units = '-';
                tempCanSignal.isLittleEndian = false;
                bool has_bits = 0;

                tempCanSignal.name.assign(signal.key().str, signal.key().len);
                for (auto const &signalParam : signal.children()) {
                    if (signalParam.key() == "type") {
                        signalParam >> tempCanSignal.type;
                    } else if (signalParam.key() == "factor") {
                        ryml::atof(signalParam.val(), &tempCanSignal.scale);
                    } else if (signalParam.key() == "offset") {
                        ryml::atoi(signalParam.val(), &tempCanSignal.offset);
                    } else if (signalParam.key() == "min") {
                        ryml::atoi(signalParam.val(), &tempCanSignal.min);
                    } else if (signalParam.key() == "max") {
                        ryml::atoi(signalParam.val(), &tempCanSignal.max);
                    } else if (signalParam.key() == "units") {
                        signalParam >> tempCanSignal.units;
                    } else if (signalParam.key() == "comment") {
                        if (signalParam.has_child("en")) {
                            signalParam["en"] >> tempCanSignal.comment;
                        } else {
                            std::cout << "Signal [" << tempCanSignal.name <<
                                "] has no comment in language [en].\n";
                        }
                    } else if (signalParam.key() == "values") {
                        for (ryml::ConstNodeRef const &value : signalParam.children()) {
                            CanSignalMeaning tempSignMeaning;
                            ryml::atox(value.key(), &tempSignMeaning.value);
                            if (value.has_child("en")) {
                                value["en"] >> tempSignMeaning.valueMeaning;
                            } else if (value.has_child("unused")) {
                                tempSignMeaning.valueMeaning = "_UNUSED";
                            } else {
                                std::cout << "Signal [" << tempCanSignal.name <<
                                    "] has no value description in language [en].\n";
                            }
                            tempCanSignal.values.push_back(tempSignMeaning);
                        }
                    } else {
                        std::cout << "Unknown CAN signal parameter [" << signalParam.key() << "].\n";
                    }
                }

                thisFrame.signal_list.push_back(tempCanSignal);
            }
        } else {
            std::cout << "Unknown CAN message parameter [" << tree.key(msgParamId) << "].\n";
        }
    } */

    if (thisFrame.isFrameInvalid())
    {
        std::cout << "INVALID MESSAGE " << yamlFile << ". It doesn't have ID, NAME or LENGTH field.\n";
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}

uint8_t getBitPosition(uint8_t ymlBitPos) {
    for (size_t i = 0; i < sizeof(yamlBitPosition); i++) {
        if (ymlBitPos == yamlBitPosition[i])
            return i;
    }
    std::cout << "Invalid bit position.\n";
    return 0xFF; // ERROR
}

void parseSignalPosition(std::string &textLine, CanSignal &canSignal)
{
    std::string parameter;
    splitString(textLine, '.', parameter);
    canSignal.setStartByte(stoi(parameter, nullptr, 10));
    bool endOfLine = splitString(textLine, '-', parameter);
    canSignal.setStartBit(stoi(parameter, nullptr, 10));
    if (endOfLine)
    {
        canSignal.setEndByte(canSignal.getStartByte());
        canSignal.setEndBit(canSignal.getStartBit());
    }
    else
    {
        splitString(textLine, '.', parameter);
        canSignal.setEndByte(stoi(parameter, nullptr, 10));
        canSignal.setEndBit(stoi(textLine, nullptr, 10));
    }
}

bool splitString(std::string &text, char delimiter, std::string &firstHalf)
{
    std::string temp {""};
    for (size_t i = 0; i < text.length(); i++)
    {
        if (text[i] != delimiter)
            temp += text[i];
        else
        {
            firstHalf = temp;
            text.erase(0, ++i);
            return 0;
        }
    }
    firstHalf = temp;
    return 1;
}
