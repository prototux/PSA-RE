#include "dbcController.h"
#include <algorithm>

void generateDbc(const char *filename, std::vector<CanMessage> const &canMsgList) {
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
    for (size_t msgNr = 0; msgNr < canMsgList.size(); msgNr++) {
        for (size_t senderNr = 0; senderNr < canMsgList[msgNr].senders.size(); senderNr++) {
            if (std::find(senderList.begin(), senderList.end(), canMsgList[msgNr].senders[senderNr])
            == senderList.end()) {
                senderList.push_back(canMsgList[msgNr].senders[senderNr]);
                dbcFile << canMsgList[msgNr].senders[senderNr] << " ";
            }
        }
    }
    dbcFile << std::endl;

    /* CONSTRUCTING CAN MESSAGES */
    for (size_t msgNr = 0; msgNr < canMsgList.size(); msgNr++) {
        std::cout << "Constructing CAN message [" << canMsgList[msgNr].id << "]\n";
        dbcFile << "BO_ " << canMsgList[msgNr].id << " " << canMsgList[msgNr].name
            << ": " << canMsgList[msgNr].dlc << " " << canMsgList[msgNr].senders[0] << "\n";

    /* CONSTRUCTING ALL SIGNALS IN CORRESPONDING MESSAGE */
        for (size_t signNr = 0; signNr < canMsgList[msgNr].signal_list.size(); signNr++) {
            dbcFile << "   SG_ " << canMsgList[msgNr].signal_list[signNr].name << " : "
                << canMsgList[msgNr].signal_list[signNr].startBit << "|"
                << canMsgList[msgNr].signal_list[signNr].lenInBits << "@"
                << canMsgList[msgNr].signal_list[signNr].isLittleEndian << "+ ("
                << canMsgList[msgNr].signal_list[signNr].scale << ","
                << canMsgList[msgNr].signal_list[signNr].offset << ") [0|1] \""
                << canMsgList[msgNr].signal_list[signNr].units << "\" Vector__XXX\n";
        }
        dbcFile << std::endl;
    }
    
    /* CONSTRUCTING VALUE TABLE */
    for (size_t msgNr = 0; msgNr < canMsgList.size(); msgNr++) {
        for (size_t signNr = 0; signNr < canMsgList[msgNr].signal_list.size(); signNr++) {
            if (!canMsgList[msgNr].signal_list[signNr].values.empty()) {
                dbcFile << "VAL_ " << canMsgList[msgNr].id << " "
                << canMsgList[msgNr].signal_list[signNr].name;
                for (size_t valNr = 0; valNr < canMsgList[msgNr].signal_list[signNr].values.size(); valNr++) {
                    dbcFile << " " << canMsgList[msgNr].signal_list[signNr].values[valNr].value
                        << " \"" << canMsgList[msgNr].signal_list[signNr].values[valNr].valueMeaning << "\"";
                }
                dbcFile << ";\n";
            }
        }
    }
}