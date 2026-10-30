/* Native RGB policy/protocol tests. SDK I/O replaced with RAM-only callbacks. */
#include <IOKit/hid/IOHIDManager.h>
static CFMutableDictionaryRef properties;
static CFTypeRef fake_property(IOHIDDeviceRef d,CFStringRef key){(void)d;return CFDictionaryGetValue(properties,key);}
static unsigned get_calls,sets,active,last,pending,fault,wire=1,saved;
static uint8_t sent_bodies[71][8];
static unsigned fail_set_at;
static IOReturn fake_get(IOHIDDeviceRef d,IOHIDReportType type,CFIndex id,uint8_t *b,CFIndex *length) {
    (void)d;(void)type;(void)id;++get_calls;
    memcpy(b,"DRGB",4);b[4]=(uint8_t)wire;b[5]=(uint8_t)active;b[6]=(uint8_t)last;b[7]=(uint8_t)((pending!=0)|(wire==2?saved<<1:0));if(pending)--pending;
    if(fault==3)b[0]='?';*length=fault==2?7:(fault==4&&get_calls==1)?0:8;
    return fault==1?kIOReturnTimeout:kIOReturnSuccess;
}
static IOReturn fake_set(IOHIDDeviceRef d,IOHIDReportType type,CFIndex id,const uint8_t *b,CFIndex length) {
    (void)d;(void)type;(void)id;if(sets>=71 || length!=8)return kIOReturnError;
    /* Model normal main-loop progress between paced SET requests. */
    if(pending)pending=0;
    memcpy(sent_bodies[sets++],b,8);active=b[1]!=3&&b[1]!=5;if(b[1]==4)saved=1;if(b[1]==5)saved=0;last=1;pending=1;
    return fail_set_at==sets?kIOReturnError:kIOReturnSuccess;
}
#define IOHIDDeviceGetProperty fake_property
#define IOHIDDeviceGetReport fake_get
#define IOHIDDeviceSetReport fake_set
#define main native_rgb_entry_unused
#include "rgb.c"
#undef main
#undef IOHIDDeviceGetProperty
#undef IOHIDDeviceGetReport
#undef IOHIDDeviceSetReport
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL RGB line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static void number(CFStringRef key,int n){CFNumberRef p=CFNumberCreate(NULL,kCFNumberIntType,&n);CFDictionarySetValue(properties,key,p);CFRelease(p);}
static void reset(void){memset(&io,0,sizeof(io));io.deadline=now()+8;get_calls=sets=active=last=pending=fault=fail_set_at=saved=0;wire=1;}
int main(void) {
    properties=CFDictionaryCreateMutable(NULL,0,&kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    CFStringRef keys[]={CFSTR(kIOHIDVendorIDKey),CFSTR(kIOHIDProductIDKey),CFSTR(kIOHIDVersionNumberKey),CFSTR(kIOHIDMaxFeatureReportSizeKey),CFSTR(kIOHIDPrimaryUsagePageKey),CFSTR(kIOHIDPrimaryUsageKey)};
    int values[]={0x3233,0x6301,0x9002,8,1,6};for(unsigned i=0;i<6;++i)number(keys[i],values[i]);
    CFDataRef descriptor=CFDataCreate(NULL,rgb_descriptor,sizeof(rgb_descriptor));CFDictionarySetValue(properties,CFSTR(kIOHIDReportDescriptorKey),descriptor);CFRelease(descriptor);
    CHECK(compatible(NULL));
    for(unsigned i=0;i<6;++i){number(keys[i],values[i]+7);CHECK(!compatible(NULL));CFDictionaryRemoveValue(properties,keys[i]);CHECK(!compatible(NULL));number(keys[i],values[i]);}
    number(keys[2],0x9001);reset();CHECK(!exchange(NULL,NULL) && !get_calls && !sets);number(keys[2],0x9002);
    struct request r;char *pixel[]={"rgb","--pixel","0","0","255","0","0"};CHECK(parse_request(7,pixel,&r));
    reset();CHECK(execute(NULL,&r));CHECK(sets==1 && io.accepted==1 && io.submitted==1);
    uint8_t expected[]={0xd1,1,0,0,255,0,0,0};CHECK(!memcmp(sent_bodies[0],expected,8));
    /* Synchronous report lifetime: SET returns completion, GET must return8. */
    for(unsigned problem=1;problem<=3;++problem){reset();fault=problem;CHECK(!execute(NULL,&r));CHECK(!sets);}
    reset();fault=4;CHECK(execute(NULL,&r) && sets==1);
    char *release[]={"rgb","--release"};CHECK(parse_request(2,release,&r));reset();CHECK(execute(NULL,&r));CHECK(sent_bodies[0][1]==3 && !active);
    char *bad_pixel[]={"rgb","--pixel","5","0","255","0","0"};CHECK(!parse_request(7,bad_pixel,&r));
    char *bad_num[]={"rgb","--pixel","0","0","-1","0","0"};CHECK(!parse_request(7,bad_num,&r));
    char *dup[]={"rgb","--batch","0000ff0000000000ff00"};CHECK(!parse_request(3,dup,&r));
    char *bad_hex[]={"rgb","--batch","0000gg0000"};CHECK(!parse_request(3,bad_hex,&r));
    char hex[701];for(unsigned n=0;n<70;++n)snprintf(hex+n*10,11,"%02x%02x%02x%02x%02x",n/14,n%14,n,255-n,n*3%256);
    char *batch[]={"rgb","--batch",hex};CHECK(parse_request(3,batch,&r));CHECK(r.count==70);reset();CHECK(execute(NULL,&r));CHECK(io.accepted==70 && sets==70);
    for(unsigned n=0;n<70;++n)CHECK(sent_bodies[n][2]==n/14 && sent_bodies[n][3]==n%14 && sent_bodies[n][4]==n);
    reset();fail_set_at=2;CHECK(!execute(NULL,&r));CHECK(sets==2 && io.accepted==0 && io.submitted==2);
    char *bound[]={"rgb","--device","4295664752","--pixel","0","0","1","2","3"};CHECK(parse_request(9,bound,&r) && r.expected_device==4295664752ULL);
    char *bad_device[]={"rgb","--device","-1","--release"};CHECK(!parse_request(4,bad_device,&r));
    char *fill[]={"rgb","--fill","1","2","255"};CHECK(parse_request(5,fill,&r));reset();CHECK(execute(NULL,&r));CHECK(sent_bodies[0][1]==2 && sent_bodies[0][4]==1 && sent_bodies[0][6]==255);
    char *generic[]={"rgb","--report","a0"};CHECK(!parse_request(3,generic,&r));
    char *save_batch[]={"rgb","--save-batch",hex};CHECK(parse_request(3,save_batch,&r)&&r.count==71&&r.persistent);
    reset();CHECK(!execute(NULL,&r)&&!sets&&!get_calls);
    number(keys[2],0x9003);reset();CHECK(!execute(NULL,&r)&&!sets);
    reset();wire=2;CHECK(execute(NULL,&r)&&sets==71&&io.accepted==71&&saved);CHECK(sent_bodies[70][1]==4);
    char *clear[]={"rgb","--clear-onboard"};CHECK(parse_request(2,clear,&r));reset();wire=2;saved=1;active=1;CHECK(execute(NULL,&r)&&sets==1&&!saved&&!active);
    char *short_save[]={"rgb","--save-batch","0000ff0000"};CHECK(!parse_request(3,short_save,&r));
    char *effect[]={"rgb","--effect","6","5","255","0","0"};CHECK(parse_request(7,effect,&r)&&r.native_effect);
    number(keys[2],0x9003);reset();CHECK(!execute(NULL,&r)&&!sets&&!get_calls);
    number(keys[2],0x9004);reset();CHECK(!execute(NULL,&r)&&!sets);
    reset();wire=2;CHECK(execute(NULL,&r)&&sets==1&&io.accepted==1&&sent_bodies[0][1]==6&&sent_bodies[0][2]==6);
    effect[2]="2";CHECK(!parse_request(7,effect,&r));effect[2]="6";effect[3]="0";CHECK(!parse_request(7,effect,&r));
    CHECK(parse_request(3,save_batch,&r));reset();wire=2;CHECK(execute(NULL,&r)&&saved&&sets==71);
    CFRelease(properties);puts("PASS: typed native-effect revision/handshake guards and bounds, RGB/batch bounds, duplicate rejection, stock/revision guards, 70-command batch, pending/status acknowledgement, synchronous SET completion vs exact GET length8; first failure stops batch, no colour write on handshake failure. RAM-only SDK mocks.");return 0;
}
