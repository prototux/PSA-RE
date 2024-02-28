#include "DbcController.h"
#include <iostream>
#include <algorithm>
#include <fstream>

void DbcController::generateDbc(const char *filename, std::vector<CanFrame> const &canFrameList) {
    std::ofstream dbcFile(filename, std::ofstream::out);

    dbcFile << "VERSION \"\"\n\n\n"
        "NS_ :\n"
        "    NS_DESC_\n"
        "    CM_\n"
        "    BA_DEF_\n"
        "    BA_\n"
        "    VAL_\n"
        "    CAT_DEF_\n"
        "    CAT_\n"
        "    FILTER\n"
        "    BA_DEF_DEF_\n"
        "    EV_DATA_\n"
        "    ENVVAR_DATA_\n"
        "    SGTYPE_\n"
        "    SGTYPE_VAL_\n"
        "    BA_DEF_SGTYPE_\n"
        "    BA_SGTYPE_\n"
        "    SIG_TYPE_REF_\n"
        "    VAL_TABLE_\n"
        "    SIG_GROUP_\n"
        "    SIG_VALTYPE_\n"
        "    SIGTYPE_VALTYPE_\n"
        "    BO_TX_BU_\n"
        "    BA_DEF_REL_\n"
        "    BA_REL_\n"
        "    BA_DEF_DEF_REL_\n"
        "    BU_SG_REL_\n"
        "    BU_EV_REL_\n"
        "    BU_BO_REL_\n"
        "    SG_MUL_VAL_\n\n"
        "BS_: \n";
    
    /* FINDING ALL SENDERS */
    dbcFile << "BU_: ";
    std::vector<std::string> senderList;
    for (size_t frameNr = 0; frameNr < canFrameList.size(); frameNr++) {
        std::vector<std::string> frameSenders = canFrameList[frameNr].getSenders();
        for (size_t senderNr = 0; senderNr < frameSenders.size(); senderNr++) {
            if (std::find(senderList.begin(), senderList.end(), frameSenders[senderNr]) == senderList.end()) {
                senderList.push_back(frameSenders[senderNr]);
                dbcFile << frameSenders[senderNr] << " ";
            }
        }
    }
    dbcFile << std::endl;

    /* PARSING CAN FRAME PARAMETERS */
    for (size_t frameNr = 0; frameNr < canFrameList.size(); frameNr++) {
        std::cout << "Parsing CAN message [" << canFrameList[frameNr].getHexId() << "]\n";
        dbcFile << "BO_ " << canFrameList[frameNr].getHexId() << " " << canFrameList[frameNr].getName()
            << ": " << canFrameList[frameNr].getLength() << " " << canFrameList[frameNr].getSenders().at(0) << "\n";

    /* PARSING ALL SIGNALS IN CORRESPONDING FRAME */
        std::vector<CanSignal> signalList = canFrameList[frameNr].getSignals();
        for (size_t signNr = 0; signNr < signalList.size(); signNr++) {
            CanSignal *pSignal = &signalList[signNr];

            int16_t startBit = calculateStartBit(pSignal->getStartByte(), pSignal->getStartBit());
            int16_t signalLength = calculateSignalLength(pSignal->getStartByte(),
                        pSignal->getStartBit(), pSignal->getEndByte(), pSignal->getEndBit());

            dbcFile << "   SG_ " << pSignal->getName() << " : "
                << startBit << "|"
                << signalLength << "@"
                << pSignal->getIsLittleEndian() << "+ ("
                << pSignal->getFactor() << ","
                << pSignal->getOffset() << ") [0|1] \""
                << pSignal->getUnits() << "\" Vector__XXX\n";
        }
        dbcFile << std::endl;
    }
    
    /* CONSTRUCTING VALUE TABLE */
    for (size_t frameNr = 0; frameNr < canFrameList.size(); frameNr++) {
        std::vector<CanSignal> signalList = canFrameList[frameNr].getSignals();
        for (size_t signNr = 0; signNr < signalList.size(); signNr++) {
            CanSignal *pSignal = &signalList[signNr];
            if (pSignal->getValueCount() != 0) {
                dbcFile << "VAL_ " << canFrameList[frameNr].getHexId() << " "
                    << pSignal->getName();
                for (size_t valNr = 0; valNr < pSignal->getValueCount(); valNr++) {
                    dbcFile << " " << pSignal->getValueNumber(valNr)
                        << " \"" << pSignal->getValueMeaning(valNr, "en") << "\"";
                }
                dbcFile << ";\n";
            }
        }
    }
}

int16_t DbcController::calculateStartBit(int16_t startByte, int16_t startBit)
{
    return (startByte-1)*8 + startBit;
}

int16_t DbcController::calculateSignalLength(int16_t startByte, int16_t startBit,
                                             int16_t endByte, int16_t endBit)
{
    return (endByte-startByte)*8 + startBit - endBit + 1;
}
