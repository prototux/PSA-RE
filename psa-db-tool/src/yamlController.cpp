#include "yamlController.h"
#include "ryml.hpp"
#include "ryml_std.hpp"

int parsePsaYaml(const char *yamlFile, CanMessage &parsedMsg)
{

    std::string yamlFileContent = get_file_contents(yamlFile);
    ryml::Tree yamlRoot = ryml::parse_in_place(ryml::to_substr(yamlFileContent));

    if (!yamlRoot.has_child(0, "id") ||
        !yamlRoot.has_child(0, "name") ||
        !yamlRoot.has_child(0, "length") ||
        !yamlRoot.has_child(0, "signals"))
    {
        std::cout << "Invalid message file " << yamlFile << ". It doesn't have ID, NAME, LENGTH or SIGNALS field.\n";
        return EXIT_FAILURE;
    }

    ryml::atox(yamlRoot["id"].val(), &parsedMsg.id);
    yamlRoot["name"] >> parsedMsg.name;
    ryml::atou(yamlRoot["length"].val(), &parsedMsg.dlc);

    if (yamlRoot.has_child(0, "type"))
    {
        yamlRoot["type"] >> parsedMsg.type;
    }

    if (yamlRoot.has_child(0, "periodicity"))
    {
        yamlRoot["periodicity"] >> parsedMsg.periodicity;
    }

    if (yamlRoot.has_child(0, "senders"))
    {
        ryml::NodeRef senders = yamlRoot["senders"];
        for (ryml::NodeRef const &child : senders.children())
        {
            std::string sender;
            child >> sender;
            parsedMsg.senders.push_back(sender);
        }
    }

    if (yamlRoot.has_child(0, "receivers"))
    {
        ryml::NodeRef receivers = yamlRoot["receivers"];
        for (ryml::NodeRef const &child : receivers.children())
        {
            std::string receiver;
            child >> receiver;
            parsedMsg.receivers.push_back(receiver);
        }
    }

    ryml::NodeRef signals = yamlRoot["signals"];
    for (ryml::NodeRef const &signal : signals.children())
    {
        CanSignal tempCanSignal;
        tempCanSignal.scale = 1;
        tempCanSignal.offset = 0;
        tempCanSignal.units = '-';
        tempCanSignal.isLittleEndian = false;

        tempCanSignal.name.assign(signal.key().str, signal.key().len);
        if (!signal.has_child("bits"))
        {
            std::cout << "Invalid signal <" << tempCanSignal.name << ">\n";
            return EXIT_FAILURE;
        }

        std::string bits;
        signal["bits"] >> bits;
        if (bits.length() < 4)
        {
            bits = bits.erase(1, 1);
            tempCanSignal.startBit = bigEndianBitPosition[getBitPosition(stoi(bits))];
            tempCanSignal.lenInBits = 1;
        }
        else
        {
            uint8_t bit1 = getBitPosition(stoi(bits.substr(0, 3).erase(1, 1)));
            uint8_t bit2 = getBitPosition(stoi(bits.substr(4, 3).erase(1, 1)));
            if (bit1 < bit2)
            {
                tempCanSignal.startBit = bigEndianBitPosition[bit1];
                tempCanSignal.lenInBits = bit2 - bit1 + 1;
            }
            else
            {
                std::cout << "Reversed bit order\n";
                tempCanSignal.startBit = bigEndianBitPosition[bit2];
                tempCanSignal.lenInBits = bit1 - bit2 + 1;
            }
        }

        if (signal.has_child("type"))
        {
            std::string type;
            signal["type"] >> type;
            tempCanSignal.type = type;
        }

        if (signal.has_child("factor"))
        {
            ryml::atof(signal["factor"].val(), &tempCanSignal.scale);
        }

        if (signal.has_child("offset"))
        {
            ryml::atoi(signal["offset"].val(), &tempCanSignal.offset);
        }

        if (signal.has_child("min"))
        {
            ryml::atoi(signal["min"].val(), &tempCanSignal.min);
        }

        if (signal.has_child("max"))
        {
            ryml::atoi(signal["max"].val(), &tempCanSignal.max);
        }

        if (signal.has_child("units"))
        {
            std::string units;
            signal["units"] >> units;
            tempCanSignal.units = units;
        }

        if (signal.has_child("comment"))
        {
            if (signal["comment"].has_child("en"))
            {
                std::string comment;
                signal["comment"]["en"] >> comment;
                tempCanSignal.comment = comment;
            }
        }

        if (signal.has_child("values"))
        {
            for (ryml::ConstNodeRef const &value : signal["values"].children())
            {
                CanSignalMeaning tempSignMeaning;
                ryml::atox(value.key(), &tempSignMeaning.value);
                if (value.has_child("en"))
                {
                    tempSignMeaning.valueMeaning.assign(value["en"].val().str, value["en"].val().len);
                }
                tempCanSignal.values.push_back(tempSignMeaning);
            }
        }

        parsedMsg.signal_list.push_back(tempCanSignal);
    }

    return EXIT_SUCCESS;
}

uint8_t getBitPosition(uint8_t ymlBitPos)
{
    for (size_t i = 0; i < sizeof(yamlBitPosition); i++)
    {
        if (ymlBitPos == yamlBitPosition[i])
            return i;
    }
    std::cout << "Invalid bit position\n";
    return 0xFF; // ERROR
}