/* Native callback guards exercised with synthetic memory only. */
#include <IOKit/hid/IOHIDManager.h>
static CFMutableDictionaryRef properties;
static CFTypeRef fake_property(IOHIDDeviceRef d,CFStringRef key) {
    (void)d; return CFDictionaryGetValue(properties,key);
}
#define IOHIDDeviceGetProperty fake_property
#include <IOKit/IOKitLib.h>
static io_service_t fake_service(IOHIDDeviceRef d){(void)d;return 0;}
static kern_return_t fake_entry(io_registry_entry_t d,uint64_t *entry){(void)d;*entry=123;return KERN_SUCCESS;}
#define IOHIDDeviceGetService fake_service
#define IORegistryEntryGetRegistryEntryID fake_entry
#define main native_client_entry_unused
#include "writer.c"
#undef main
#undef IOHIDDeviceGetProperty
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL callback line %d\n",__LINE__);exit(1);}} while(0)
static void reset(void) {memset(&live,0,sizeof(live));live.active=1;}
static void prop_number(CFStringRef key,int v) {
    CFNumberRef n=CFNumberCreate(NULL,kCFNumberIntType,&v);
    CFDictionarySetValue(properties,key,n); CFRelease(n);
}
static void identity_tests(void) {
    expected_entry=123;expected_location=1048576;
    properties=CFDictionaryCreateMutable(NULL,0,&kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    CFStringRef keys[]={CFSTR(kIOHIDVendorIDKey),CFSTR(kIOHIDProductIDKey),CFSTR(kIOHIDLocationIDKey),
        CFSTR(kIOHIDPrimaryUsagePageKey),CFSTR(kIOHIDPrimaryUsageKey),
        CFSTR(kIOHIDMaxInputReportSizeKey),CFSTR(kIOHIDMaxOutputReportSizeKey)};
    int values[]={0x0416,0x3f00,1048576,0xff00,1,64,64};
    for(unsigned i=0;i<7;++i) prop_number(keys[i],values[i]);
    CFDataRef data=CFDataCreate(NULL,descriptor,sizeof(descriptor));
    CFDictionarySetValue(properties,CFSTR(kIOHIDReportDescriptorKey),data); CFRelease(data);
    CHECK(identity_ok(NULL));expected_entry=124;CHECK(!identity_ok(NULL));expected_entry=123;
    for(unsigned i=0;i<7;++i) {
        prop_number(keys[i],values[i]+1); CHECK(!identity_ok(NULL));
        CFDictionarySetValue(properties,keys[i],CFSTR("wrong type")); CHECK(!identity_ok(NULL));
        CFDictionaryRemoveValue(properties,keys[i]); CHECK(!identity_ok(NULL));
        prop_number(keys[i],values[i]);
    }
    uint8_t wrong[sizeof(descriptor)];memcpy(wrong,descriptor,sizeof(wrong));wrong[0]^=1;
    data=CFDataCreate(NULL,wrong,sizeof(wrong));
    CFDictionarySetValue(properties,CFSTR(kIOHIDReportDescriptorKey),data);CFRelease(data);
    CHECK(!identity_ok(NULL));
    reset(); uint8_t tx[64],rx[64];size_t len=0;chosen=image_job(0);fixed_request(&chosen,0,tx);
    CHECK(!exchange(NULL,0,tx,rx,&len));CHECK(live.submitted==0);
    CFRelease(properties);
}
int main(void) {
    uint8_t b[64]={0};
    reset(); input(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeInput,0,b,64);
    CHECK(live.input_done && !live.failed);
    input(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeInput,0,b,64); CHECK(live.failed);
    reset();live.active=0;input(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeInput,0,b,64);CHECK(live.failed);
    reset();input(NULL,kIOReturnError,NULL,kIOHIDReportTypeInput,0,b,64);CHECK(live.failed);
    reset();input(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeOutput,0,b,64);CHECK(live.failed);
    reset();input(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeInput,1,b,64);CHECK(live.failed);
    reset();input(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeInput,0,b,63);CHECK(live.failed);
    reset();input(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeInput,0,b,65);CHECK(live.failed);
    reset();sent(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeOutput,0,b,64);CHECK(live.write_done && !live.failed);
    sent(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeOutput,0,b,64);CHECK(live.failed);
    reset();sent(NULL,kIOReturnError,NULL,kIOHIDReportTypeOutput,0,b,64);CHECK(live.failed);
    reset();live.active=0;sent(NULL,kIOReturnSuccess,NULL,kIOHIDReportTypeOutput,0,b,64);CHECK(live.failed);
    reset();removed(NULL,kIOReturnSuccess,NULL);CHECK(live.failed);
    identity_tests();
    puts("PASS: input type/ID/length/error/duplicate/inactive guards; write completion guards; removal; identity property/type/missing/descriptor guards, zero sends on mismatch. No device APIs invoked.");
    return 0;
}
