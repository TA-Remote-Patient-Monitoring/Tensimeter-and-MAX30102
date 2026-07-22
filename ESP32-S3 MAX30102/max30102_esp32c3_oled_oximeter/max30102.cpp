#include "max30102.h"
#include <Wire.h>

bool maxim_max30102_init(int sda_pin, int scl_pin) {
  Wire.begin(sda_pin, scl_pin);
  if (!maxim_max30102_write_reg(REG_INTR_ENABLE_1, 0xc0)) // INTR setting
    return false;
  if (!maxim_max30102_write_reg(REG_INTR_ENABLE_2, 0x00))
    return false;
  if (!maxim_max30102_write_reg(REG_FIFO_WR_PTR, 0x00)) // FIFO_WR_PTR[4:0]
    return false;
  if (!maxim_max30102_write_reg(REG_OVF_COUNTER, 0x00)) // OVF_COUNTER[4:0]
    return false;
  if (!maxim_max30102_write_reg(REG_FIFO_RD_PTR, 0x00)) // FIFO_RD_PTR[4:0]
    return false;
  if (!maxim_max30102_write_reg(REG_FIFO_CONFIG, 0x4f)) // sample avg = 4, fifo rollover=false, fifo temp empty=15
    return false;
  if (!maxim_max30102_write_reg(REG_MODE_CONFIG, 0x03)) // 0x02 for Red only, 0x03 for SpO2 mode, 0x07 multi-LED mode
    return false;
  if (!maxim_max30102_write_reg(REG_SPO2_CONFIG, 0x27)) // SPO2_ADC range = 4096nA, SPO2 sample rate (100 Hz), LED pulseWidth (411uS)
    return false;

  if (!maxim_max30102_write_reg(REG_LED1_PA, 0x24)) // Choose value for ~7mA for LED1
    return false;
  if (!maxim_max30102_write_reg(REG_LED2_PA, 0x24)) // Choose value for ~7mA for LED2
    return false;
  if (!maxim_max30102_write_reg(REG_PILOT_PA, 0x7f)) // Choose value for ~25mA for Pilot LED
    return false;
  return true;
}

bool maxim_max30102_read_fifo(uint32_t *pun_red_led, uint32_t *pun_ir_led) {
  uint32_t un_temp;
  uint8_t uch_temp;
  *pun_red_led = 0;
  *pun_ir_led = 0;
  
  if (!maxim_max30102_read_reg(REG_INTR_STATUS_1, &uch_temp))
    return false;
  if (!maxim_max30102_read_reg(REG_INTR_STATUS_2, &uch_temp))
    return false;
    
  Wire.beginTransmission(I2C_WRITE_ADDR);
  Wire.write(REG_FIFO_DATA);
  if (Wire.endTransmission() != 0)
    return false;
    
  Wire.requestFrom(I2C_READ_ADDR, 6);
  if (Wire.available() >= 6) {
    un_temp = Wire.read();
    un_temp <<= 16;
    *pun_red_led += un_temp;
    un_temp = Wire.read();
    un_temp <<= 8;
    *pun_red_led += un_temp;
    un_temp = Wire.read();
    *pun_red_led += un_temp;
    
    un_temp = Wire.read();
    un_temp <<= 16;
    *pun_ir_led += un_temp;
    un_temp = Wire.read();
    un_temp <<= 8;
    *pun_ir_led += un_temp;
    un_temp = Wire.read();
    *pun_ir_led += un_temp;
    
    *pun_red_led &= 0x03FFFF;
    *pun_ir_led &= 0x03FFFF;
    return true;
  }
  return false;
}

bool maxim_max30102_write_reg(uint8_t uch_addr, uint8_t uch_data) {
  Wire.beginTransmission(I2C_WRITE_ADDR);
  Wire.write(uch_addr);
  Wire.write(uch_data);
  return (Wire.endTransmission() == 0);
}

bool maxim_max30102_read_reg(uint8_t uch_addr, uint8_t *puch_data) {
  Wire.beginTransmission(I2C_WRITE_ADDR);
  Wire.write(uch_addr);
  if (Wire.endTransmission() != 0)
    return false;
  Wire.requestFrom(I2C_READ_ADDR, 1);
  if (Wire.available() >= 1) {
    *puch_data = Wire.read();
    return true;
  }
  return false;
}

bool maxim_max30102_reset(void) {
  if (!maxim_max30102_write_reg(REG_MODE_CONFIG, 0x40))
    return false;
  return true;
}

bool maxim_max30102_read_temperature(int8_t *integer_part, uint8_t *fractional_part) {
  maxim_max30102_write_reg(REG_TEMP_CONFIG, 0x01);
  delay(1);
  uint8_t temp_int = 0, temp_frac = 0;
  if (maxim_max30102_read_reg(REG_TEMP_INTR, &temp_int) &&
      maxim_max30102_read_reg(REG_TEMP_FRAC, &temp_frac)) {
    *integer_part = (int8_t)temp_int;
    *fractional_part = temp_frac;
    return true;
  }
  return false;
}
