#include "yamlController.h"
#include "ryml.hpp"
#include "ryml_std.hpp"

int parsePsaYaml(const char *yamlFile, CanMessage &parsedMsg) {

    std::string yamlFileContent = get_file_contents(yamlFile);
    ryml::Tree yamlRoot = ryml::parse_in_place(ryml::to_substr(yamlFileContent));

    bool has_id = 0, has_name = 0, has_length = 0, has_signals = 0;

    for (size_t msgParamId = yamlRoot.first_child(yamlRoot.root_id()); msgParamId != ryml::NONE;
                msgParamId = yamlRoot.next_sibling(msgParamId)) {
        if (yamlRoot.key(msgParamId) == "id") {
            ryml::atox(yamlRoot["id"].val(), &parsedMsg.id);
            has_id = true;
        } else if (yamlRoot.key(msgParamId) == "name") {
            yamlRoot["name"] >> parsedMsg.name;
            has_name = true;
        } else if (yamlRoot.key(msgParamId) == "length") {
            ryml::atou(yamlRoot["length"].val(), &parsedMsg.dlc);
            has_length = true;
        } else if (yamlRoot.key(msgParamId) == "type") {
            yamlRoot["type"] >> parsedMsg.type;
        } else if (yamlRoot.key(msgParamId) == "periodicity") {
            yamlRoot["periodicity"] >> parsedMsg.periodicity;
        } else if (yamlRoot.key(msgParamId) == "senders") {
            ryml::NodeRef senders = yamlRoot["senders"];
            for (ryml::NodeRef const &child : senders.children()) {
                std::string sender;
                child >> sender;
                parsedMsg.senders.push_back(sender);
            }
        } else if (yamlRoot.key(msgParamId) == "receivers") {
            ryml::NodeRef receivers = yamlRoot["receivers"];
            for (ryml::NodeRef const &child : receivers.children()) {
                std::string receiver;
                child >> receiver;
                parsedMsg.receivers.push_back(receiver);
            }
        } else if (yamlRoot.key(msgParamId) == "signals") {
            has_signals = true;
            ryml::NodeRef signals = yamlRoot["signals"];
            for (ryml::NodeRef const &signal : signals.children()) {
                CanSignal tempCanSignal;
                tempCanSignal.scale = 1;
                tempCanSignal.offset = 0;
                tempCanSignal.units = '-';
                tempCanSignal.isLittleEndian = false;
                bool has_bits = 0;

                tempCanSignal.name.assign(signal.key().str, signal.key().len);
                for (auto const &signalParam : signal.children()) {
                    if (signalParam.key() == "bits") {
                        has_bits = true;
                        std::string bits;
                        bits.assign(signalParam.val().str, signalParam.val().len);
                        if (bits.length() < 4) {
                            bits = bits.erase(1, 1);
                            tempCanSignal.startBit = bigEndianBitPosition[getBitPosition(stoi(bits))];
                            tempCanSignal.lenInBits = 1;
                        } else {
                            uint8_t bit1 = getBitPosition(stoi(bits.substr(0, 3).erase(1, 1)));
                            uint8_t bit2 = getBitPosition(stoi(bits.substr(4, 3).erase(1, 1)));
                            if (bit1 < bit2) {
                                tempCanSignal.startBit = bigEndianBitPosition[bit1];
                                tempCanSignal.lenInBits = bit2 - bit1 + 1;
                            } else {
                                std::cout << "NOTE: Reversed bit order in signal [" << tempCanSignal.name << "].\n";
                                tempCanSignal.startBit = bigEndianBitPosition[bit2];
                                tempCanSignal.lenInBits = bit1 - bit2 + 1;
                            }
                        }
                    } else if (signalParam.key() == "type") {
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

                parsedMsg.signal_list.push_back(tempCanSignal);
                if (!has_bits) {
                    std::cout << "INVALID SIGNAL. Doesn't have field [bits].\n";
                }
            }
        } else {
            std::cout << "Unknown CAN message parameter [" << yamlRoot.key(msgParamId) << "].\n";
        }
    }

    if (has_id && has_name && has_length && has_signals) {
        return EXIT_SUCCESS;
    } else {
        std::cout << "INVALID MESSAGE " << yamlFile << ". It doesn't have ID, NAME, LENGTH or SIGNALS field.\n";
        return EXIT_FAILURE;
    }
}

uint8_t getBitPosition(uint8_t ymlBitPos) {
    for (size_t i = 0; i < sizeof(yamlBitPosition); i++) {
        if (ymlBitPos == yamlBitPosition[i])
            return i;
    }
    std::cout << "Invalid bit position.\n";
    return 0xFF; // ERROR
}
