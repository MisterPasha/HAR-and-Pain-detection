// Arduino Wire library is required if I2Cdev I2CDEV_ARDUINO_WIRE implementation
// is used in I2Cdev.h
#include "Wire.h"

// I2Cdev, AK8975, and MPU6050 must be installed as libraries, or else the
// .cpp/.h files for all classes must be in the include path of your project
#include "I2Cdev.h"
#include "AK8975.h"
#include "MPU6050.h"
#include "RFduinoBLE.h"

AK8975 mag(0x0C);
MPU6050 accelgyro(0x68); // address = 0x68, the default, on MPU6050 EVB

// accelerometer, gyro, and magnetometer values
int16_t ax, ay, az;
int16_t gx, gy, gz;
int16_t mx, my, mz;
float heading;

void setup() {
  // join I2C bus (I2Cdev library doesn't do this automatically)
  Wire.begin();
  // initialize serial communication
  Serial.begin(9600);
  // initialize MPU first so we can connect the AUX lines
  accelgyro.initialize();
  accelgyro.setI2CBypassEnabled(true);
  mag.initialize();

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

  RFduinoBLE.advertisementData = "Hi"; // shouldnt be more than 10 characters long
  RFduinoBLE.deviceName = device2[0]; // name of your RFduino. Will appear when other BLE enabled devices search for it
  RFduinoBLE.customUUID = device2[1];
  //Serial.println("BLE Start Setup");
  RFduinoBLE.begin(); // begin
}

//  Use the following global variables and access functions
//  to calibrate the acceleration sensor
float    base_x_accel;
float    base_y_accel;
float    base_z_accel;

float    base_x_gyro;
float    base_y_gyro;
float    base_z_gyro;

// The sensor should be motionless on a horizontal surface
//  while calibration is happening
void calibrate_sensors() {

  int                   num_readings = 10;
  float                 x_accel = 0;
  float                 y_accel = 0;
  float                 z_accel = 0;
  float                 x_gyro = 0;
  float                 y_gyro = 0;
  float                 z_gyro = 0;

  // Discard the first set of values read from the IMU
  accelgyro.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

  // Read and average the raw values from the IMU
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
  x_accel /= num_readings;
  y_accel /= num_readings;
  z_accel /= num_readings;
  x_gyro /= num_readings;
  y_gyro /= num_readings;
  z_gyro /= num_readings;

  // Store the raw calibration values globally
  base_x_accel = x_accel;
  base_y_accel = y_accel;
  base_z_accel = z_accel;
  base_x_gyro = x_gyro;
  base_y_gyro = y_gyro;
  base_z_gyro = z_gyro;
}

unsigned long connection_time; // used to count offset for syncronic connection

struct CompactSensorData {
  uint32_t accGyrTime; // Time in microseconds
  uint32_t magTime;    // Time in microseconds
};

struct CompactSensorData2 {
  uint32_t allSensTime; // Time in microseconds
};


unsigned long previousMillis = 0; // Store the last time sensor data was sent
const unsigned long interval = 25; // Interval between sending data (in milliseconds)

void loop() {
  unsigned long currentMillis = millis();

  // Check if the interval has elapsed
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis; // Update the previousMillis

    unsigned long currentTimeMicros = micros();
    
    // Read raw magnetometer measurements from the device
    mag.getHeading(&mx, &my, &mz);
    //uint32_t magTime = (uint32_t)(micros() - currentTimeMicros); // Convert to 16-bit safely

    // currentTimeMicros = micros();
    
    // Read raw accel/gyro measurements from the device
    accelgyro.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
    //uint32_t accGyrTime = (uint32_t)(micros() - currentTimeMicros); // Convert to 16-bit safely
    uint32_t allSensTime = (uint32_t)(micros() - currentTimeMicros);

    // Prepare and send sensor data over BLE
    // CompactSensorData data = {accGyrTime, magTime};
    CompactSensorData2 data = {allSensTime};
    RFduinoBLE.send((const char*)&data, sizeof(data));
  }

  // Perform other non-blocking tasks here if needed
}

void RFduinoBLE_onConnect(){

  calibrate_sensors();
  connection_time = millis();  // Record the time when BLE connection starts

}
