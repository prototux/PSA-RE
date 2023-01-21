#ifndef PARSE_PSA_YAML
#define PARSE_PSA_YAML

#include "fileController.h"
#include "dataStructures.h"

const uint8_t yamlBitPosition[64] =
    {17, 16, 15, 14, 13, 12, 11, 10,
    27, 26, 25, 24, 23, 22, 21, 20,
    37, 36, 35, 34, 33, 32, 31, 30,
    47, 46, 45, 44, 43, 42, 41, 40,
    57, 56, 55, 54, 53, 52, 51, 50,
    67, 66, 65, 64, 63, 62, 61, 60,
    77, 76, 75, 74, 73, 72, 71, 70,
    87, 86, 85, 84, 83, 82, 81, 80,
    };

uint8_t getBitPosition(uint8_t ymlBitPos);
int parsePsaYaml(const char *yamlFile, CanMessage &parsedMsg);

#endif  // PARSE_PSA_YAML