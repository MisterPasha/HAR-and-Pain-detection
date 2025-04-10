// Arduino Wire library is required if I2Cdev I2CDEV_ARDUINO_WIRE implementation is used
#include "Wire.h"

// I2Cdev, AK8975, and MPU6050 must be installed as libraries
#include "I2Cdev.h"
#include "AK8975.h"
#include "MPU6050.h"
#include "RFduinoBLE.h"

AK8975 mag(0x0C);
MPU6050 accelgyro(0x68); // Default I2C address

// Raw sensor values
int16_t ax, ay, az;
int16_t gx, gy, gz;
int16_t mx, my, mz;

// Scaled sensor values
float ax_s, ay_s, az_s;
float gx_s, gy_s, gz_s;
float mx_s, my_s, mz_s;

float heading;

void setup() {
  // Initialize I2C communication
  Wire.begin();
  Serial.begin(9600);

  // Initialize MPU6050 and magnetometer
  accelgyro.initialize();
  accelgyro.setI2CBypassEnabled(true); // Enable bypass to access magnetometer
  mag.initialize();

  // Configure BLE advertisement settings
  char* device1[] = {"RThigh", "12340014-cbed-76db-9423-74ce6ab51dee"};
  char* device2[] = {"RArm", "12340014-cbed-76db-9423-74ce6ab52dee"};
  char* device3[] = {"LArm", "12340014-cbed-76db-9423-74ce6ab53dee"};
  char* device4[] = {"LThigh", "12340014-cbed-76db-9423-74ce6ab54dee"};
  char* device5[] = {"Head", "12340014-cbed-76db-9423-74ce6ab55dee"};
  char* device6[] = {"Back", "12340014-cbed-76db-9423-74ce6ab56dee"};
  char* device7[] = {"LShank", "12340014-cbed-76db-9423-74ce6ab57dee"};
  char* device9[] = {"RShank", "12340014-cbed-76db-9423-74ce6ab59dee"};
  char* device10[] = {"Extra", "12340014-cbed-76db-9424-74ce6ab50dee"};
  char* device11[] = {"Extra2", "12340014-cbed-76db-9424-74ce6ab51dee"};
  
  RFduinoBLE.advertisementData = "Hi"; // Limited to 10 characters
  RFduinoBLE.deviceName = device7[0];  // BLE device name
  RFduinoBLE.customUUID = device7[1];

  Serial.print("Sensor Name is: ");
  Serial.println(RFduinoBLE.deviceName);

  RFduinoBLE.begin(); // Start BLE communication
}

  // Calibration values
float base_x_accel, base_y_accel, base_z_accel;
float base_x_gyro, base_y_gyro, base_z_gyro;
float mag_x_offset, mag_y_offset, mag_z_offset;
float mag_x_scale = 1, mag_y_scale = 1, mag_z_scale = 1;  // Avoid division by zero

void calibrate_sensors() {
  Serial.println("Calibrating AccelGyro, hold still!");

  int num_readings = 10;
  float x_accel = 0, y_accel = 0, z_accel = 0;
  float x_gyro = 0, y_gyro = 0, z_gyro = 0;

  accelgyro.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  delay(100);  // Give sensor time to stabilize

  for (int i = 0; i < num_readings; i++) {
    accelgyro.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
    x_accel += ax;
    y_accel += ay;
    z_accel += az;
    x_gyro += gx;
    y_gyro += gy;
    z_gyro += gz;
    delay(100);
  }

  base_x_accel = x_accel / num_readings;
  base_y_accel = y_accel / num_readings;
  base_z_accel = z_accel / num_readings;
  base_x_gyro = x_gyro / num_readings;
  base_y_gyro = y_gyro / num_readings;
  base_z_gyro = z_gyro / num_readings;

  Serial.println("AccelGyro calibrating Done!");
  Serial.print("Base X Accel: ");
  Serial.println(base_x_accel);
  Serial.print("Base Y Accel: ");
  Serial.println(base_y_accel);
  Serial.print("Base Z Accel: ");
  Serial.println(base_z_accel);
  Serial.print("Base X Gyro: ");
  Serial.println(base_x_gyro);
  Serial.print("Base Y Gyro: ");
  Serial.println(base_y_gyro);
  Serial.print("Base Z Gyro: ");
  Serial.println(base_z_gyro);
}

void calibrate_magnetometer() {
  int num_readings = 500;
  int16_t mx_raw, my_raw, mz_raw;
  int16_t mag_x_min = 32767, mag_x_max = -32767;
  int16_t mag_y_min = 32767, mag_y_max = -32767;
  int16_t mag_z_min = 32767, mag_z_max = -32767;

  Serial.println("Starting magnetometer calibration...");
  Serial.println("--Rotate sensor in all directions--");
  
  for (int i = 0; i < num_readings; i++) {
    mag.getHeading(&mx_raw, &my_raw, &mz_raw);

    if (mx_raw < mag_x_min) mag_x_min = mx_raw;
    if (mx_raw > mag_x_max) mag_x_max = mx_raw;
    if (my_raw < mag_y_min) mag_y_min = my_raw;
    if (my_raw > mag_y_max) mag_y_max = my_raw;
    if (mz_raw < mag_z_min) mag_z_min = mz_raw;
    if (mz_raw > mag_z_max) mag_z_max = mz_raw;

    delay(50);
  }

  mag_x_offset = (mag_x_max + mag_x_min) / 2.0;
  mag_y_offset = (mag_y_max + mag_y_min) / 2.0;
  mag_z_offset = (mag_z_max + mag_z_min) / 2.0;

  mag_x_scale = (mag_x_max - mag_x_min) / 2.0;
  mag_y_scale = (mag_y_max - mag_y_min) / 2.0;
  mag_z_scale = (mag_z_max - mag_z_min) / 2.0;

  if (mag_x_scale == 0) mag_x_scale = 1;
  if (mag_y_scale == 0) mag_y_scale = 1;
  if (mag_z_scale == 0) mag_z_scale = 1;

  Serial.println("Magnetometer calibration is Done!");
  Serial.print("Mag X Offset: ");
  Serial.println(mag_x_offset);
  Serial.print("Mag Y Offset: ");
  Serial.println(mag_y_offset);
  Serial.print("Mag Z Offset: ");
  Serial.println(mag_z_offset);
  Serial.print("Mag X Scale: ");
  Serial.println(mag_x_scale);
  Serial.print("Mag Y Scale: ");
  Serial.println(mag_y_scale);
  Serial.print("Mag Z Scale: ");
  Serial.println(mag_z_scale);
  
}
// BLE data structure for transmission
struct CompactSensorData {
  float ax, ay, az;
  float gx, gy, gz;
  float mx, my, mz;
};

// Timing variables
unsigned long previousMillis = 0;
const unsigned long interval = 25; // 25ms interval

void loop() {
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    // Read raw sensor values
    mag.getHeading(&mx, &my, &mz);
    accelgyro.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

    // Apply accelerometer scaling
    ax_s = (ax - base_x_accel) / 16384.0;
    ay_s = (ay - base_y_accel) / 16384.0;
    az_s = (az - base_z_accel) / 16384.0;
    // Apply gyroscope scaling
    gx_s = (gx - base_x_gyro) / 131.0;
    gy_s = (gy - base_y_gyro) / 131.0;
    gz_s = (gz - base_z_gyro) / 131.0;

    // Apply magnetometer calibration
    mx_s = (mx - mag_x_offset) / mag_x_scale;
    my_s = (my - mag_y_offset) / mag_y_scale;
    mz_s = (mz - mag_z_offset) / mag_z_scale;

    // Send scaled data over BLE
    CompactSensorData data = {ax_s, ay_s, az_s, gx_s, gy_s, gz_s, mx_s, my_s, mz_s};
    RFduinoBLE.send((const char*)&data, sizeof(data));
  }
}

// BLE connection callback
void RFduinoBLE_onConnect() {
  calibrate_sensors();
  calibrate_magnetometer();
}
