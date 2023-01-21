cmake_minimum_required(VERSION 3.12)
project(psaDbTool LANGUAGES CXX VERSION 0.1)

add_subdirectory(submodules/rapidyaml ryml)
# find_package(ryml REQUIRED)

add_executable(psaDbTool psaDbTool.cpp yamlController.cpp fileController.cpp dbcController.cpp)
target_link_libraries(psaDbTool ryml::ryml)

add_custom_target(run psaDbTool
    COMMAND $<TARGET_FILE:psaDbTool>
    DEPENDS psaDbTool
    COMMENT "running: $<TARGET_FILE:psaDbTool>")

# cmake_minimum_required(VERSION 3.12)
# project(parsePsaYaml LANGUAGES CXX VERSION 0.1)

# add_subdirectory(submodules/rapidyaml ryml)
# # find_package(ryml REQUIRED)

# add_executable(parsePsaYaml parsePsaYaml.cpp)
# target_link_libraries(parsePsaYaml ryml::ryml)

# add_custom_target(run parsePsaYaml
#     COMMAND $<TARGET_FILE:parsePsaYaml>
#     DEPENDS parsePsaYaml
#     COMMENT "running: $<TARGET_FILE:parsePsaYaml>")
