#ifndef DBC_CONTROLLER
#define DBC_CONTROLLER

#include "dataStructures.h"
#include "fileController.h"

void generateDbc(const char *filename, std::vector<CanMessage> const &canMsgList);

#endif  // DBC_CONTROLLER