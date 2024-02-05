cmake_minimum_required(VERSION 3.12)
project(psaDbTool LANGUAGES CXX VERSION 0.1)

add_subdirectory(submodules/rapidyaml ryml)
# find_package(ryml REQUIRED)

SET(GCC_COVERAGE_COMPILE_FLAGS "-g")

SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${GCC_COVERAGE_COMPILE_FLAGS}")

add_executable(psaDbTool psaDbTool.cpp dbmuxeController.cpp fileController.cpp dbcController.cpp CanFrame.cpp CanSignal.cpp LanguageField.cpp)
target_link_libraries(psaDbTool ryml::ryml)

add_custom_target(run psaDbTool
    COMMAND $<TARGET_FILE:psaDbTool>
    DEPENDS psaDbTool
    COMMENT "running: $<TARGET_FILE:psaDbTool>")
