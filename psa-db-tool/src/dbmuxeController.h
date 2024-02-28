#ifndef PARSE_PSA_YAML
#define PARSE_PSA_YAML

#include "fileController.h"
#include "CanFrame.h"


int parsePsaYaml(const char *yamlFile, CanFrame &parsedMsg);

/**
 * @brief Parse all signal position parameters using textLine from YAML file
 * @param textLine - string from YAML file
 * @param canSignal - object where parsed data will be written
*/
void parseSignalPosition(std::string &textLine, CanSignal &canSignal);

/**
 * @brief Splits string into two strings separated by first delimiter symbol
 * @param text - reference to input text. At the end it will lose the beginning till delimiter
 * @param delimiter - separation symbol
 * @param firstHalf - reference where 1st half of text will be stored
 * @retval 0 if delimiter found, 1 - not found
*/
bool splitString(std::string &text, char delimiter, std::string &firstHalf);

#endif  // PARSE_PSA_YAML