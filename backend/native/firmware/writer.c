/* Experimental macOS coordinator transport, derived from physically tested research.
   Defaults to offline plan. Browser approval, fixed image hashes and chip/config guards are required. */
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDManager.h>
#include <IOKit/hid/IOHIDKeys.h>
#include <stdio.h>
#include <IOKit/IOKitLib.h>
#include <CommonCrypto/CommonDigest.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <time.h>
#include "protocol.h"

static const uint8_t descriptor[]={0x06,0x00,0xff,0x09,0x01,0xa1,0x01,0x19,0x01,0x29,0x40,0x15,0x00,0x26,0xff,0x00,0x75,0x08,0x95,0x40,0x81,0x00,0x19,0x01,0x29,0x40,0x91,0x00,0xc0};
/* Static lifetime keeps async buffers/context valid even during error cleanup. */
static struct job chosen;
static uint64_t expected_entry;
static int expected_location;
static int inspect_only;
static struct {
    IOHIDDeviceRef device;
    uint8_t input_buffer[64],tx[64],reply[64];
    int active,failed,write_done,input_done;
    unsigned submitted;
} live;

static double monotonic_seconds(void) {
    struct timespec t;
    if(clock_gettime(CLOCK_MONOTONIC,&t)!=0) return -1;
    return (double)t.tv_sec+(double)t.tv_nsec/1e9;
}

static void packet(const char *event,const uint8_t *b,size_t n) {
    printf("{\"event\":\"%s\",\"body_hex\":\"",event);
    for(size_t i=0;i<n;++i) printf("%02x",b[i]);
    puts("\"}"); fflush(stdout);
}
static int property_is(IOHIDDeviceRef d,CFStringRef key,int wanted) {
    CFTypeRef p=IOHIDDeviceGetProperty(d,key); int v=0;
    return p && CFGetTypeID(p)==CFNumberGetTypeID()
        && CFNumberGetValue((CFNumberRef)p,kCFNumberIntType,&v) && v==wanted;
}
static int identity_ok(IOHIDDeviceRef d) {
    uint64_t entry=0;
    if(IORegistryEntryGetRegistryEntryID(IOHIDDeviceGetService(d),&entry)!=KERN_SUCCESS || entry!=expected_entry)return 0;
    CFTypeRef p=IOHIDDeviceGetProperty(d,CFSTR(kIOHIDReportDescriptorKey));
    return property_is(d,CFSTR(kIOHIDVendorIDKey),0x0416)
        && property_is(d,CFSTR(kIOHIDProductIDKey),0x3f00)
        && property_is(d,CFSTR(kIOHIDLocationIDKey),expected_location)
        && property_is(d,CFSTR(kIOHIDPrimaryUsagePageKey),0xff00)
        && property_is(d,CFSTR(kIOHIDPrimaryUsageKey),1)
        && property_is(d,CFSTR(kIOHIDMaxInputReportSizeKey),64)
        && property_is(d,CFSTR(kIOHIDMaxOutputReportSizeKey),64)
        && p && CFGetTypeID(p)==CFDataGetTypeID()
        && CFDataGetLength((CFDataRef)p)==sizeof(descriptor)
        && memcmp(CFDataGetBytePtr((CFDataRef)p),descriptor,sizeof(descriptor))==0;
}
static void input(void *ctx,IOReturn result,void *sender,IOHIDReportType type,
                  uint32_t reportID,uint8_t *report,CFIndex length) {
    (void)ctx; (void)sender;
    if(result!=kIOReturnSuccess || !live.active || live.input_done
       || type!=kIOHIDReportTypeInput || reportID!=0 || length!=64) {
        live.failed=1; return;
    }
    memcpy(live.reply,report,64); live.input_done=1; packet("received",report,64);
}
static void sent(void *ctx,IOReturn result,void *sender,IOHIDReportType type,
                 uint32_t reportID,uint8_t *report,CFIndex length) {
    (void)ctx;(void)sender;(void)type;(void)reportID;(void)report;(void)length;
    if(result!=kIOReturnSuccess || !live.active || live.write_done) live.failed=1;
    else live.write_done=1;
}
static void removed(void *ctx,IOReturn result,void *sender) {
    (void)ctx;(void)result;(void)sender; live.failed=1;
}
static int exchange(void *ctx,unsigned step,const uint8_t tx[64],uint8_t rx[64],size_t *len) {
    (void)ctx; uint8_t expected[64];
    if(live.failed || step!=live.submitted || step>=report_count(&chosen) || !identity_ok(live.device)
       || !fixed_request(&chosen,step,expected) || memcmp(tx,expected,64)!=0) return 0;
    /* Handle any queued unexpected input/removal before sending another packet. */
    CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.01,false);
    if(live.failed) return 0;
    double start=monotonic_seconds();
    if(start<0) return 0;
    live.active=1; live.write_done=0; live.input_done=0;
    memcpy(live.tx,tx,64); ++live.submitted;
    packet("submitting",live.tx,64);
    /* Report ID passed separately: descriptor has no report-ID item.
       No leading zero byte is included in the 64-byte report body. */
    IOReturn r=IOHIDDeviceSetReportWithCallback(live.device,kIOHIDReportTypeOutput,
                    0,live.tx,64,step>=3?25000.0:1000.0,sent,NULL);
    if(r!=kIOReturnSuccess) { live.failed=1; live.active=0; return 0; }
    double deadline=start+(step>=3?30.0:3.0);
    while(!live.failed && !(live.write_done && live.input_done)
          && monotonic_seconds()>=0 && monotonic_seconds()<deadline)
        CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.02,true);
    live.active=0;
    if(live.failed || !live.write_done || !live.input_done) {live.failed=1;return 0;}
    memcpy(rx,live.reply,64); *len=64;
    return 1;
}
static int run_live(int restore) {
    chosen=image_job(restore);
    IOHIDManagerRef manager=IOHIDManagerCreate(kCFAllocatorDefault,kIOHIDOptionsTypeNone);
    if(!manager) return 1;
    int vid=0x0416,pid=0x3f00;
    CFNumberRef v=CFNumberCreate(NULL,kCFNumberIntType,&vid),p=CFNumberCreate(NULL,kCFNumberIntType,&pid);
    const void *keys[]={CFSTR(kIOHIDVendorIDKey),CFSTR(kIOHIDProductIDKey)};
    const void *values[]={v,p};
    CFDictionaryRef match=CFDictionaryCreate(NULL,keys,values,2,&kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    IOHIDManagerSetDeviceMatching(manager,match);
    CFRelease(match); CFRelease(v); CFRelease(p);
    CFSetRef devices=IOHIDManagerCopyDevices(manager);
    if(!devices || CFSetGetCount(devices)!=1) {
        fputs("STOP: expected exactly one 0416:3F00 HID device. No reports sent.\n",stderr);
        if(devices) CFRelease(devices); CFRelease(manager); return 1;
    }
    const void *device=NULL; CFSetGetValues(devices,&device); live.device=(IOHIDDeviceRef)device;
    if(!identity_ok(live.device)) {
        fputs("STOP: selected interface, descriptor or connection changed. No reports sent.\n",stderr);
        CFRelease(devices); CFRelease(manager); return 1;
    }
    if(IOHIDDeviceOpen(live.device,kIOHIDOptionsTypeNone)!=kIOReturnSuccess) {
        fputs("STOP: device open failed. No reports sent; no permission escalation.\n",stderr);
        CFRelease(devices); CFRelease(manager); return 1;
    }
    IOHIDDeviceRegisterInputReportCallback(live.device,live.input_buffer,64,input,NULL);
    IOHIDDeviceRegisterRemovalCallback(live.device,removed,NULL);
    IOHIDDeviceScheduleWithRunLoop(live.device,CFRunLoopGetCurrent(),kCFRunLoopDefaultMode);
    struct progress progress; int ok=program_aprom(&chosen,exchange,NULL,&progress,inspect_only);
    IOHIDDeviceUnscheduleFromRunLoop(live.device,CFRunLoopGetCurrent(),kCFRunLoopDefaultMode);
    IOHIDDeviceClose(live.device,kIOHIDOptionsTypeNone);
    CFRelease(devices); CFRelease(manager);
    printf("{\"event\":\"program_result\",\"ok\":%s,\"image_sha256\":\"%s\",\"submitted\":%u,\"acknowledged\":%u,\"bytes_acknowledged\":%zu,\"aprom_attempted\":%s}\n",
        ok?"true":"false",chosen.sha256,progress.submitted,progress.acknowledged,progress.bytes_acknowledged,progress.aprom_attempted?"true":"false");
    if(ok) fputs("All requested packets acknowledged with checksum/sequence checks. This is not a full-flash readback or hash verification.\n",stderr);
    else fputs("STOP: exchange failed. No retries or fallback commands.\n",stderr);
    fputs("Do not assume a failed update left a runnable application. Follow the reviewed physical reconnect/restore procedure; no automatic reset or restore is sent.\n",stderr);
    return ok?0:1;
}

static int devices_cached(void) {
    IOHIDManagerRef manager=IOHIDManagerCreate(NULL,kIOHIDOptionsTypeNone);
    if(!manager)return 1;
    int vid=0x0416,pid=0x3f00;
    CFNumberRef v=CFNumberCreate(NULL,kCFNumberIntType,&vid),p=CFNumberCreate(NULL,kCFNumberIntType,&pid);
    const void *keys[]={CFSTR(kIOHIDVendorIDKey),CFSTR(kIOHIDProductIDKey)};
    const void *values[]={v,p};
    CFDictionaryRef match=CFDictionaryCreate(NULL,keys,values,2,&kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    IOHIDManagerSetDeviceMatching(manager,match);CFRelease(match);CFRelease(v);CFRelease(p);
    CFSetRef devices=IOHIDManagerCopyDevices(manager);int ok=0;
    if(devices && CFSetGetCount(devices)==1) {
        const void *d=NULL;CFSetGetValues(devices,&d);
        CFTypeRef loc=IOHIDDeviceGetProperty((IOHIDDeviceRef)d,CFSTR(kIOHIDLocationIDKey));
        if(loc && CFGetTypeID(loc)==CFNumberGetTypeID() && CFNumberGetValue((CFNumberRef)loc,kCFNumberIntType,&expected_location)
           && IORegistryEntryGetRegistryEntryID(IOHIDDeviceGetService((IOHIDDeviceRef)d),&expected_entry)==KERN_SUCCESS && expected_entry && identity_ok((IOHIDDeviceRef)d))ok=1;
    }
    if(ok)printf("{\"ok\":true,\"loader\":{\"device_id\":\"%llu\",\"location\":%d}}\n",(unsigned long long)expected_entry,expected_location);
    else puts("{\"ok\":true,\"loader\":null}");
    if(devices)CFRelease(devices);CFRelease(manager);return 0;
}
static int number(const char *text,uint64_t *value) {
    if(!*text || *text=='-' || *text=='+')return 0;
    for(const char *p=text;*p;++p)if(*p<'0'||*p>'9')return 0;
    errno=0;char *end=NULL;*value=strtoull(text,&end,10);
    return !errno && end && !*end && *value;
}
static int load_image(const char *path,int restore) {
    struct job j=image_job(restore);FILE *f=fopen(path,"rb");if(!f)return 0;
    uint8_t *buffer=restore?restore_image:candidate_image;
    size_t n=fread(buffer,1,j.length,f);int extra=fgetc(f);int error=ferror(f);fclose(f);
    if(n!=j.length || extra!=EOF || error)return 0;
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];char actual[65];
    CC_SHA256(buffer,(CC_LONG)j.length,digest);
    for(unsigned i=0;i<32;++i)sprintf(actual+i*2,"%02x",digest[i]);
    return strcmp(actual,j.sha256)==0;
}
int main(int argc,char **argv) {
    if(argc==1 || (argc==2 && strcmp(argv[1],"--plan")==0)) {
        puts("OFFLINE: fixed custom9002 or manufacturer1.10 APROM only. No device APIs. No embedded manufacturer images.");return 0;
    }
    if(argc==2 && strcmp(argv[1],"--devices")==0)return devices_cached();
    inspect_only=argc==4 && strcmp(argv[1],"--inspect")==0;
    int restore=argc==5 && strcmp(argv[1],"--program-restore")==0;
    int candidate=argc==5 && strcmp(argv[1],"--program-candidate")==0;
    uint64_t loc=0;
    if((!inspect_only && !restore && !candidate) || !number(argv[2],&expected_entry) || !number(argv[3],&loc) || loc>INT_MAX)return 2;
    expected_location=(int)loc;
    /* Verify the exact approved image independently before any HID device is opened. */
    if(!inspect_only && !load_image(argv[4],restore)){fputs("Image hash/size mismatch. No device APIs.\n",stderr);return 2;}
    return run_live(restore);
}
