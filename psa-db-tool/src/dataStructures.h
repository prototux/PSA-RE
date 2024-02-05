#ifndef DATA_STRUCTURES
#define DATA_STRUCTURES

#include <string>
#include <vector>

// typedef struct
// {
//     short value;
//     std::string valueMeaning;
// } CanSignalMeaning;

// typedef struct
// {
//     std::string name;
//     std::string comment;
//     std::string type;
//     short startBit;
//     short lenInBits;
//     bool isLittleEndian;
//     float scale;
//     int offset;
//     int min;
//     int max;
//     std::string units;
//     std::vector<CanSignalMeaning> values;
// } CanSignal;

typedef struct
{
    unsigned id;
    std::string name;
    std::vector<std::string> alt_name;
    unsigned short dlc;
    std::vector<std::string> comment;
    std::string type;
    std::string periodicity;
    std::vector<std::string> senders;
    std::vector<std::string> receivers;
    // std::vector<CanSignal> signal_list;
} CanMessage;

const uint8_t bigEndianBitPosition[64] =
    {7, 6, 5, 4, 3, 2, 1, 0,
    15,14,13,12,11,10, 9, 8,
    23,22,21,20,19,18,17,16,
    31,30,29,28,27,26,25,24,
    39,38,37,36,35,34,33,32,
    47,46,45,44,43,42,41,40,
    55,54,53,52,51,50,49,48,
    63,62,61,60,59,58,57,56
    };

#endif // DATA_STRUCTURES