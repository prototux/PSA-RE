#pragma once

#include "CanFrame.h"

class DbcController
{
public:
    DbcController() = default;
    ~DbcController() = default;

    void generateDbc(const char *filename, std::vector<CanFrame> const &canFrameList);

private:
    int16_t calculateStartBit(int16_t startByte, int16_t startBit);

    int16_t calculateSignalLength(int16_t startByte, int16_t startBit,
                                  int16_t endByte, int16_t endBit);
    
};



