// Immobilizer challenge-response implementation
// This should match the authentication between the BSI and the engine ECU
// The protocol is pretty simple:
// * On frame 0x72 (ECU to BSI): 0x00 (4 bytes of challenge)
// * On frame 0xA8 (BSI to ECU): 0x04 (4 bytes of response)
// * If the challenge is accepted: {0x00, 0x00, 0x00, 0x00, 0x00} on frame 0x72
// Thanks a lot to Wouter Bokslag for the original work and algorithm :)

#include <inttypes.h>

// Transformation function with PSA not-so-secret sauce
int16_t transform(uint8_t data_msb, uint8_t data_lsb, uint8_t sec[])
{
	int16_t data = (data_msb << 8) | data_lsb;
	int32_t result = ((data % sec[0]) * sec[2]) - ((data / sec[0]) * sec[1]);
	if (result < 0)
		result += (sec[0] * sec[2]) + sec[1];
	return result;
}

// Challenge reponse calculation for a given pin and challenge
// Challenge and pin are both 4*8bits values
uint32_t compute_response(uint8_t pin[], uint8_t chg[])
{
	// Hardcoded secrets...
	int8_t sec_1[3] = {0xB2, 0x3F, 0xAA};
	int8_t sec_2[3] = {0xB1, 0x02, 0xAB};

	// Compute each 16bits part of the response and return it
	int16_t res_msb = transform(chg[0], chg[2], sec_1) | transform(pin[0], pin[3], sec_2);
	int16_t res_lsb = transform(chg[1], chg[3], sec_2) | transform(pin[1], pin[2], sec_1);
	return (res_msb << 16) | res_lsb;
}
