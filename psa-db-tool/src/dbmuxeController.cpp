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
        }
        else if (frameParam.key() == "comment")
        {
            for (ryml::ConstNodeRef const& comment : frameParam.children())
            {
                std::string tempCommentText {comment.val().str, comment.val().len};
                LanguageField tempComment(comment.key().begin(), tempCommentText);
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
                tempCanSignal.setFactor(1.0);   // By default Factor = 1
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
                    else if (signalParam.key() == "comment")
                    {
                        std::vector<LanguageField> tempCommentTranslations;
                        for (ryml::ConstNodeRef const& translation : signalParam.children())
                        {
                            std::string tempTranslation(translation.val().str, translation.val().len);
                            LanguageField tempLangField(translation.key().begin(), tempTranslation);
                            tempCommentTranslations.push_back(tempLangField);
                        }
                        tempCanSignal.setComment(tempCommentTranslations);
                    }
                    else if (signalParam.key() == "values")
                    {
                        for (ryml::ConstNodeRef const& value : signalParam.children())
                        {
                            std::vector<LanguageField> tempSignalValueMeanings;
                            for (ryml::ConstNodeRef const &valueMeaning : value.children())
                            {
                                std::string tempMeaningDescription(valueMeaning.val().str, valueMeaning.val().len);
                                LanguageField tempLangField(valueMeaning.key().begin(), tempMeaningDescription);
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
            std::cout << "Unknown CAN frame parameter [" << frameParam.key() << "].\n";
        }
    }

    if (thisFrame.isFrameInvalid())
    {
        std::cout << "INVALID CAN FRAME " << yamlFile << ".\n";
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
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
