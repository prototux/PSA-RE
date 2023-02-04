#include "dbmuxeController.h"
#include "dbcController.h"
#include <string.h>
#include <dirent.h>
#include <chrono>

enum Command { NONE, LOAD_FILE, LOAD_DIR, GENERATE_DBC };

inline void print_usage(void);

inline void print_can_message(CanMessage canMessage);

int main(int argc, char const *argv[]) {
    if (argc < 2) {
        print_usage();
        return EXIT_SUCCESS;
    }
    
    Command execCommand = NONE;
    std::vector<CanMessage> parsedMsgList;
    bool verbose_print = false;

    auto start_time = std::chrono::high_resolution_clock::now();
    for (size_t argNr = 1; argNr < argc; argNr++) {
        if ('-' == argv[argNr][0]) {            // COMMAND SELECTION
            if (!strcmp("-help", argv[argNr]) || !strcmp("--help", argv[argNr]) || !strcmp("-h", argv[argNr])) {
                print_usage();
                return EXIT_SUCCESS;
            } else if (!strcmp("-Lf", argv[argNr])) {
                execCommand = LOAD_FILE;
            } else if (!strcmp("-Ld", argv[argNr])) {
                execCommand = LOAD_DIR;
            } else if (!strcmp("-Gd", argv[argNr])) {
                execCommand = GENERATE_DBC;
            } else if (!strcmp("-v", argv[argNr])) {
                verbose_print = true;
            } else {
                std::cout << "Command " << argv[argNr] << " is not recognized by psaDbTool.\n";
                print_usage();
                return EXIT_SUCCESS;
            }
        } else {                                // ARGUMENTS CAPTURE
            switch (execCommand) {
                case NONE:
                    std::cout << "You have to select a command first. Then give args.";
                    print_usage();
                    return EXIT_SUCCESS;
                    break;
                case LOAD_FILE:
                    std::cout << "  - Loading file [" << argv[argNr] << "].\n";
                    parsedMsgList.emplace_back();
                    parsePsaYaml(argv[argNr], parsedMsgList.at(parsedMsgList.size() - 1));
                    break;
                case LOAD_DIR:
                    std::cout << "  - Loading directory [" << argv[argNr] << "].\n";
                    DIR *p_inputFileDir;
                    struct dirent *p_inputFileDirStruct;
                    p_inputFileDir = opendir(argv[argNr]);
                    if (p_inputFileDir == nullptr) {
                        std::cout << "Directory [" << argv[argNr] << "] doesn't exist.\n";
                        return EXIT_FAILURE;
                    }
                    while ((p_inputFileDirStruct = readdir(p_inputFileDir)) != nullptr) {
                        if ('.' == p_inputFileDirStruct->d_name[0] || !strstr(p_inputFileDirStruct->d_name, ".yml"))
                            continue;
                        parsedMsgList.emplace_back();
                        std::cout << "File in dir: " << p_inputFileDirStruct->d_name << ".\n";
                        char fullFileName[256];
                        strcpy(fullFileName, argv[argNr]);
                        strcat(fullFileName, p_inputFileDirStruct->d_name);
                        parsePsaYaml(fullFileName, parsedMsgList.at(parsedMsgList.size() - 1));
                    }
                    break;
                case GENERATE_DBC:
                    std::cout << "  - Generating DBC [" << argv[argNr] << "]\n";
                    generateDbc(argv[argNr], parsedMsgList);
                    break;
                default:
                    std::cout << "This should never happen...";
                    break;
            }
        }
    }

// PRINT WHAT WE COLLECTED FROM YAML FILES
    if (verbose_print) {
        for (size_t i = 0; i < parsedMsgList.size(); i++) {
            print_can_message(parsedMsgList.at(i));
        }
    }
    
    auto stop_time = std::chrono::high_resolution_clock::now();
    auto execute_time = std::chrono::duration_cast<std::chrono::microseconds>(stop_time - start_time);
    std::cout << "Time taken to complete: " << execute_time.count() << " microseconds.\n";

    return EXIT_SUCCESS;
}

void print_usage(void) {
    std::cout << "Usage:\n"
         << "  psaDbTool [options]\n"
         << "  psaDbTool [options] [options]\n"
         << "  psaDbTool [options] [options] [options]...\n\n"
         << "Options\n"
         << "  -Lf <path-to-file1> <path-to-file2>...           = Loads YAML files.\n"
         << "  -Ld <path-to-directory1> <path-to-directory2>... = Loads all YAML files in directory.\n"
         << "  -Gd <DBC-filename-with-path>                     = Generates DBC file.\n"
         << "  -v                                               = Verbosely list collected information.\n"
         << "Examples\n"
         << "  ./psaDbTool -Ld ../../../buses/AEE2004.full/HS.IS/ -Gd ./HS_IS.dbc\n"
         << "  ./psaDbTool -Lf ../../../buses/AEE2004.full/HS.IS/0A8.yml "
         << "../../../buses/AEE2004.full/HS.IS/072.yml -Gd ./immo.dbc\n";
}

void print_can_message(CanMessage canMessage) {
    std::cout << "CAN_ID: " << canMessage.id << std::endl;
    std::cout << "NAME: " << canMessage.name << std::endl;
    std::cout << "DLC: " << canMessage.dlc << std::endl;
    std::cout << "TYPE: " << canMessage.type << std::endl;
    std::cout << "PERIOD: " << canMessage.periodicity << std::endl;
    std::cout << "SENDERS:" << std::endl;
    for (auto sender : canMessage.senders) {
        std::cout << "   -" << sender << "-\n";
    }
    std::cout << "RECEIVERS:" << std::endl;
    for (auto receiver : canMessage.receivers) {
        std::cout << "   -" << receiver << "-\n";
    }
    std::cout << "SIGNALS:" << std::endl;
    for (size_t signNr = 0; signNr < canMessage.signal_list.size(); signNr++) {
        std::cout << "   -" << canMessage.signal_list[signNr].name << 
        "-  START_BIT: " << canMessage.signal_list[signNr].startBit <<
        "   LENGTH_BIT: " << canMessage.signal_list[signNr].lenInBits <<
        "   TYPE: " << canMessage.signal_list[signNr].type <<
        "   SCALE: " << canMessage.signal_list[signNr].scale <<
        "   OFFSET: " << canMessage.signal_list[signNr].offset <<
        "   MIN: " << canMessage.signal_list[signNr].min <<
        "   MAX: " << canMessage.signal_list[signNr].max <<
        "   UNITS: " << canMessage.signal_list[signNr].units <<
        "   COMMENT: " << canMessage.signal_list[signNr].comment <<
        "   VALUES:\n";
        for (size_t valNr = 0; valNr < canMessage.signal_list[signNr].values.size(); valNr++) {
            std::cout << "      ~ " << canMessage.signal_list[signNr].values[valNr].value
            << ":  " << canMessage.signal_list[signNr].values[valNr].valueMeaning << std::endl;
        }
    }
}