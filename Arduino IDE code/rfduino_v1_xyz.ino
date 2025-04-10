
// I2C device class (I2Cdev) demonstration Arduino sketch for AK8975 class
// 6/11/2012 by Jeff Rowberg <jeff@rowberg.net>
// Updates should (hopefully) always be available at https://github.com/jrowberg/i2cdevlib
//
// This example uses the AK8975 as mounted on the InvenSense MPU-6050 Evaluation
// Board, and as such also depends (minimally) on the MPU6050 library from the
// I2Cdevlib collection. It initializes the MPU6050 and immediately enables its
// "I2C Bypass" mode, which allows the sketch to communicate with the AK8975
// that is attached to the MPU's AUX SDA/SCL lines. The AK8975 is configured on
// this board to use the 0x0E address.
//
// Note that this small demo does not make use of any of the MPU's amazing
// motion processing capabilities (the DMP); it only provides raw sensor access
// to the compass as mounted on that particular evaluation board.
//
// For more info on the MPU-6050 and some more impressive demos, check out the
// device page on the I2Cdevlib website:
//     http://www.i2cdevlib.com/devices/mpu6050
//
// Changelog:
//     2012-06-11 - initial release

/* ============================================
I2Cdev device library code is placed under the MIT license
Copyright (c) 2012 Jeff Rowberg
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
===============================================
*/

// Arduino Wire library is required if I2Cdev I2CDEV_ARDUINO_WIRE implementation
// is used in I2Cdev.h
#include "Wire.h"

// I2Cdev, AK8975, and MPU6050 must be installed as libraries, or else the
// .cpp/.h files for all classes must be in the include path of your project
#include "I2Cdev.h"
#include "AK8975.h"
#include "MPU6050.h"
#include "RFduinoBLE.h"


// class default I2C address is 0x0C
// specific I2C addresses may be passed as a parameter here
// Addr pins low/low = 0x0C
// Addr pins low/high = 0x0D
// Addr pins high/low = 0x0E (default for InvenSense MPU6050 evaluation board)
// Addr pins high/high = 0x0F

AK8975 mag(0x0C);
MPU6050 accelgyro(0x68); // address = 0x68, the default, on MPU6050 EVB


// accelerometer, gyro, and magnetometer values
int16_t ax, ay, az;
int16_t gx, gy, gz;
int16_t mx, my, mz;
float heading;


void setup() {
    override_uart_limit = true; 

    // join I2C bus (I2Cdev library doesn't do this automatically)
    Wire.begin();

    // initialize serial communication
    // (38400 chosen because it works as well at 8MHz as it does at 16MHz, but
    // it's really up to you depending on your project)
    Serial.begin(9600);

    // initialize devices
    Serial.println("Initializing I2C devices...");
    
    // initialize MPU first so we can connect the AUX lines
    accelgyro.initialize();
    accelgyro.setI2CBypassEnabled(true);
    
    Serial.println(F("Testing device connections to MPU6050..."));
    Serial.println(accelgyro.testConnection() ? F("MPU6050 connection successful") : F("MPU6050 connection failed"));  
    
    mag.initialize();
    
    // verify connection
    Serial.println("Testing device connections to AK8975...");
    Serial.println(mag.testConnection() ? "AK8975 connection successful" : "AK8975 connection failed");
    
        
    char* device0[] = {"emgR", "12340014-cbed-76db-9423-74ce6ab50dee"};
    char* device1[] = {"RThigh", "12340014-cbed-76db-9423-74ce6ab51dee"};
    char* device2[] = {"RArm", "12340014-cbed-76db-9423-74ce6ab52dee"};
    char* device3[] = {"LArm", "12340014-cbed-76db-9423-74ce6ab53dee"};
    char* device4[] = {"LThigh", "12340014-cbed-76db-9423-74ce6ab54dee"};
    char* device5[] = {"Head", "12340014-cbed-76db-9423-74ce6ab55dee"};
    char* device6[] = {"Back", "12340014-cbed-76db-9423-74ce6ab56dee"};
    char* device7[] = {"LShank", "12340014-cbed-76db-9423-74ce6ab57dee"};    
    char* device8[] = {"emgL", "12340014-cbed-76db-9423-74ce6ab58dee"};
    char* device9[] = {"RShank", "12340014-cbed-76db-9423-74ce6ab59dee"};
    char* device10[] = {"Extra", "12340014-cbed-76db-9424-74ce6ab50dee"};    
    char* device11[] = {"Extra2", "12340014-cbed-76db-9424-74ce6ab51dee"};
    char* device12[] = {"emgExtra", "12340014-cbed-76db-9424-74ce6ab52dee"};
    char* device13[] = {"emgExtra2", "12340014-cbed-76db-9424-74ce6ab53dee"};
    
    
    RFduinoBLE.advertisementData = "Hi"; // shouldnt be more than 10 characters long
    
    RFduinoBLE.deviceName = device10[0]; // name of your RFduino. Will appear when other BLE enabled devices search for it 
    RFduinoBLE.customUUID = device10[1];
    
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
  
  Serial.println(F("Calibrating sensors..."));
  int                   num_readings = 10;
  float                 x_accel = 0;
  float                 y_accel = 0;
  float                 z_accel = 0;
  float                 x_gyro = 0;
  float                 y_gyro = 0;
  float                 z_gyro = 0;
  
  
  //Serial.println("Starting Calibration");

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
  
  Serial.println("Finishing Calibration");
}


// Use the following global variables and access functions to help store the overall
// rotation angle of the sensor
unsigned long last_read_time;
float         last_x_angle;  // These are the filtered angles
float         last_y_angle;
float         last_z_angle;  
float         last_gyro_x_angle;  // Store the gyro angles to compare drift
float         last_gyro_y_angle;
float         last_gyro_z_angle;

void set_last_read_angle_data(unsigned long time, float x, float y, float z, float x_gyro, float y_gyro, float z_gyro) {
  last_read_time = time;
  last_x_angle = x;
  last_y_angle = y;
  last_z_angle = z;
  last_gyro_x_angle = x_gyro;
  last_gyro_y_angle = y_gyro;
  last_gyro_z_angle = z_gyro;
}

inline unsigned long get_last_time() {return last_read_time;}
inline float get_last_x_angle() {return last_x_angle;}
inline float get_last_y_angle() {return last_y_angle;}
inline float get_last_z_angle() {return last_z_angle;}
inline float get_last_gyro_x_angle() {return last_gyro_x_angle;}
inline float get_last_gyro_y_angle() {return last_gyro_y_angle;}
inline float get_last_gyro_z_angle() {return last_gyro_z_angle;}

//constants
float RADIANS_TO_DEGREES = 180/3.14159;
float accel_angle_z = 0;
float FS_SEL = 131;
float alpha = 0.995;


void loop() {

  
    // read raw heading measurements from device
    mag.getHeading(&mx, &my, &mz);
    
    // read raw accel/gyro measurements from device
    accelgyro.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

    // these methods (and a few others) are also available
    //accelgyro.getAcceleration(&ax, &ay, &az);
    //accelgyro.getRotation(&gx, &gy, &gz);
    
     // Get the time of reading for rotation computations
    unsigned long t_now = millis();
    
    // Convert gyro values to degrees/sec
    //float FS_SEL = 131;
  
    float gyro_x = (gx - base_x_gyro)/FS_SEL;
    float gyro_y = (gy - base_y_gyro)/FS_SEL;
    float gyro_z = (gz - base_z_gyro)/FS_SEL;
    
    
    // Get raw acceleration values
    //float G_CONVERT = 16384;
    float accel_x = ax;
    float accel_y = ay;
    float accel_z = az;
    
    // Get angle values from accelerometer
    //float RADIANS_TO_DEGREES = 180/3.14159;
    //  float accel_vector_length = sqrt(pow(accel_x,2) + pow(accel_y,2) + pow(accel_z,2));
    float accel_angle_y = atan(-1*accel_x/sqrt(pow(accel_y,2) + pow(accel_z,2)))*RADIANS_TO_DEGREES;
    float accel_angle_x = atan(accel_y/sqrt(pow(accel_x,2) + pow(accel_z,2)))*RADIANS_TO_DEGREES;
  
    //float accel_angle_z = 0;
    
    // Compute the (filtered) gyro angles
    float dt =(t_now - get_last_time())/1000.0;
    float gyro_angle_x = gyro_x*dt + get_last_x_angle();
    float gyro_angle_y = gyro_y*dt + get_last_y_angle();
    float gyro_angle_z = gyro_z*dt + get_last_z_angle();
    
    // Compute the drifting gyro angles
    float unfiltered_gyro_angle_x = gyro_x*dt + get_last_gyro_x_angle();
    float unfiltered_gyro_angle_y = gyro_y*dt + get_last_gyro_y_angle();
    float unfiltered_gyro_angle_z = gyro_z*dt + get_last_gyro_z_angle();
    
    // Apply the complementary filter to figure out the change in angle - choice of alpha is
    // estimated now.  Alpha depends on the sampling rate...
    //float alpha = 0.995; 
    float angle_x = alpha*gyro_angle_x + (1.0 - alpha)*accel_angle_x;
    float angle_y = alpha*gyro_angle_y + (1.0 - alpha)*accel_angle_y;
    float angle_z = gyro_angle_z;  //Accelerometer doesn't give z-angle
    
    // Update the saved data with the latest values
    set_last_read_angle_data(t_now, angle_x, angle_y, angle_z, unfiltered_gyro_angle_x, unfiltered_gyro_angle_y, unfiltered_gyro_angle_z);
    
    String timeString = String(t_now);
    timeString += " ";
    timeString +=String(int(angle_x));
    timeString += " ";
    timeString +=String(int(angle_y));;
    //timeString += " ";
    //timeString +=String(int(angle_z));
    
    char data[timeString.length()];
    timeString.toCharArray(data, timeString.length()+1);
    
    RFduinoBLE.send(data, sizeof(data));  
    
    //Serial.println(int(angle_y));
    delay(5);


}

void RFduinoBLE_onConnect(){
  
      void calibrate_sensors();
 
}

