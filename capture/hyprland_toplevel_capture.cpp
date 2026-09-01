// Small, dependency-light client for Hyprland's clean toplevel capture API.
// The Python application reads the AWC1 header followed by RGBA pixels.

#include <wayland-client.h>
#include <wayland-client-protocol.h>

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#include "hyprland-toplevel-export-v1-client-protocol.h"

namespace {

struct RegistryState {
    wl_shm* shm = nullptr;
    hyprland_toplevel_export_manager_v1* manager = nullptr;
};

struct FrameState {
    uint32_t format = 0;
    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t stride = 0;
    uint32_t flags = 0;
    bool got_buffer = false;
    bool got_buffer_done = false;
    bool ready = false;
    bool failed = false;
};

void registry_global(void* data, wl_registry* registry, uint32_t name,
                    const char* interface, uint32_t version) {
    auto* state = static_cast<RegistryState*>(data);
    if (std::strcmp(interface, "wl_shm") == 0 && !state->shm) {
        state->shm = static_cast<wl_shm*>(wl_registry_bind(
            registry, name, &wl_shm_interface, std::min(version, 1u)));
    } else if (std::strcmp(interface, "hyprland_toplevel_export_manager_v1") == 0
               && !state->manager) {
        state->manager = static_cast<hyprland_toplevel_export_manager_v1*>(wl_registry_bind(
            registry, name, &hyprland_toplevel_export_manager_v1_interface,
            std::min(version, 1u)));
    }
}

void registry_global_remove(void*, wl_registry*, uint32_t) {}

const wl_registry_listener REGISTRY_LISTENER = {
    registry_global,
    registry_global_remove,
};

void frame_buffer(void* data, hyprland_toplevel_export_frame_v1*, uint32_t format,
                  uint32_t width, uint32_t height, uint32_t stride) {
    auto* state = static_cast<FrameState*>(data);
    if (!state->got_buffer) {
        state->format = format;
        state->width = width;
        state->height = height;
        state->stride = stride;
        state->got_buffer = true;
    }
}

void frame_damage(void*, hyprland_toplevel_export_frame_v1*, uint32_t, uint32_t,
                  uint32_t, uint32_t) {}

void frame_flags(void* data, hyprland_toplevel_export_frame_v1*, uint32_t flags) {
    static_cast<FrameState*>(data)->flags = flags;
}

void frame_ready(void* data, hyprland_toplevel_export_frame_v1*, uint32_t, uint32_t,
                 uint32_t) {
    static_cast<FrameState*>(data)->ready = true;
}

void frame_failed(void* data, hyprland_toplevel_export_frame_v1*) {
    static_cast<FrameState*>(data)->failed = true;
}

void frame_linux_dmabuf(void*, hyprland_toplevel_export_frame_v1*, uint32_t, uint32_t,
                        uint32_t) {}

void frame_buffer_done(void* data, hyprland_toplevel_export_frame_v1*) {
    static_cast<FrameState*>(data)->got_buffer_done = true;
}

const hyprland_toplevel_export_frame_v1_listener FRAME_LISTENER = {
    frame_buffer,
    frame_damage,
    frame_flags,
    frame_ready,
    frame_failed,
    frame_linux_dmabuf,
    frame_buffer_done,
};

int make_shared_memory_fd() {
    int fd = -1;
#ifdef SYS_memfd_create
    fd = static_cast<int>(syscall(SYS_memfd_create, "awc-toplevel", MFD_CLOEXEC));
    if (fd >= 0) {
        return fd;
    }
#endif

    char path[] = "/tmp/awc-toplevel-XXXXXX";
    fd = mkstemp(path);
    if (fd >= 0) {
        unlink(path);
        fcntl(fd, F_SETFD, FD_CLOEXEC);
    }
    return fd;
}

bool write_all(const void* data, size_t size) {
    const auto* bytes = static_cast<const uint8_t*>(data);
    while (size > 0) {
        ssize_t written = write(STDOUT_FILENO, bytes, size);
        if (written <= 0) {
            return false;
        }
        bytes += written;
        size -= static_cast<size_t>(written);
    }
    return true;
}

bool output_rgba(const FrameState& frame, const void* mapped) {
    if (!mapped || frame.width == 0 || frame.height == 0 || frame.stride < frame.width * 4) {
        return false;
    }

    struct Header {
        char magic[4];
        uint32_t width;
        uint32_t height;
        uint32_t stride;
    } header{{'A', 'W', 'C', '1'}, frame.width, frame.height, frame.width * 4};
    if (!write_all(&header, sizeof(header))) {
        return false;
    }

    const bool y_invert = (frame.flags & HYPRLAND_TOPLEVEL_EXPORT_FRAME_V1_FLAGS_Y_INVERT) != 0;
    uint8_t* row = new (std::nothrow) uint8_t[static_cast<size_t>(frame.width) * 4];
    if (!row) {
        return false;
    }

    bool supported = frame.format == WL_SHM_FORMAT_ARGB8888
                  || frame.format == WL_SHM_FORMAT_XRGB8888
                  || frame.format == WL_SHM_FORMAT_ABGR8888
                  || frame.format == WL_SHM_FORMAT_XBGR8888
                  || frame.format == WL_SHM_FORMAT_RGBA8888
                  || frame.format == WL_SHM_FORMAT_RGBX8888;
    if (!supported) {
        delete[] row;
        return false;
    }

    for (uint32_t y = 0; y < frame.height; ++y) {
        uint32_t source_y = y_invert ? frame.height - y - 1 : y;
        const auto* source = static_cast<const uint8_t*>(mapped) +
                             static_cast<size_t>(source_y) * frame.stride;
        for (uint32_t x = 0; x < frame.width; ++x) {
            const uint8_t* pixel = source + static_cast<size_t>(x) * 4;
            uint8_t* output = row + static_cast<size_t>(x) * 4;
            if (frame.format == WL_SHM_FORMAT_ARGB8888 || frame.format == WL_SHM_FORMAT_XRGB8888) {
                output[0] = pixel[2];
                output[1] = pixel[1];
                output[2] = pixel[0];
                output[3] = frame.format == WL_SHM_FORMAT_ARGB8888 ? pixel[3] : 255;
            } else if (frame.format == WL_SHM_FORMAT_ABGR8888 || frame.format == WL_SHM_FORMAT_XBGR8888) {
                output[0] = pixel[3];
                output[1] = pixel[2];
                output[2] = pixel[1];
                output[3] = frame.format == WL_SHM_FORMAT_ABGR8888 ? pixel[0] : 255;
            } else {
                output[0] = pixel[0];
                output[1] = pixel[1];
                output[2] = pixel[2];
                output[3] = frame.format == WL_SHM_FORMAT_RGBA8888 ? pixel[3] : 255;
            }
        }
        if (!write_all(row, static_cast<size_t>(frame.width) * 4)) {
            delete[] row;
            return false;
        }
    }
    delete[] row;
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: awc-hyprland-toplevel-capture WINDOW_ADDRESS\n");
        return 2;
    }

    char* end = nullptr;
    unsigned long long parsed = std::strtoull(argv[1], &end, 0);
    if (!end || *end != '\0') {
        std::fprintf(stderr, "invalid Hyprland window address: %s\n", argv[1]);
        return 2;
    }

    // `hyprctl clients` prints a native-width hexadecimal address while the
    // version-1 Wayland protocol accepts its lower 32-bit handle. Rejecting a
    // normal 64-bit address made every clean capture fail on current systems.
    const uint32_t handle = static_cast<uint32_t>(parsed);

    wl_display* display = wl_display_connect(nullptr);
    if (!display) {
        std::fprintf(stderr, "could not connect to Wayland\n");
        return 1;
    }

    RegistryState registry_state;
    wl_registry* registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &REGISTRY_LISTENER, &registry_state);
    if (wl_display_roundtrip(display) < 0 || !registry_state.shm || !registry_state.manager) {
        std::fprintf(stderr, "Hyprland clean window capture protocol is unavailable\n");
        wl_display_disconnect(display);
        return 1;
    }

    FrameState frame_state;
    auto* frame = hyprland_toplevel_export_manager_v1_capture_toplevel(
        registry_state.manager, 0, handle);
    if (!frame || hyprland_toplevel_export_frame_v1_add_listener(
                     frame, &FRAME_LISTENER, &frame_state) < 0) {
        std::fprintf(stderr, "could not create Hyprland capture frame\n");
        wl_display_disconnect(display);
        return 1;
    }

    if (wl_display_roundtrip(display) < 0) {
        frame_state.failed = true;
    }
    while (!frame_state.failed && !frame_state.got_buffer_done) {
        if (wl_display_dispatch(display) < 0) {
            frame_state.failed = true;
        }
    }

    int fd = -1;
    void* mapped = MAP_FAILED;
    wl_buffer* buffer = nullptr;
    int result = 1;
    if (!frame_state.failed && frame_state.got_buffer && frame_state.width > 0 &&
        frame_state.height > 0 && frame_state.stride >= frame_state.width * 4) {
        size_t size = static_cast<size_t>(frame_state.stride) * frame_state.height;
        fd = make_shared_memory_fd();
        if (fd >= 0 && ftruncate(fd, static_cast<off_t>(size)) == 0) {
            mapped = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
            if (mapped != MAP_FAILED) {
                wl_shm_pool* pool = wl_shm_create_pool(registry_state.shm, fd,
                                                       static_cast<int32_t>(size));
                if (pool) {
                    buffer = wl_shm_pool_create_buffer(pool, 0,
                        static_cast<int32_t>(frame_state.width),
                        static_cast<int32_t>(frame_state.height),
                        static_cast<int32_t>(frame_state.stride), frame_state.format);
                    wl_shm_pool_destroy(pool);
                }
            }
        }
    }

    if (buffer) {
        hyprland_toplevel_export_frame_v1_copy(frame, buffer, 1);
        wl_display_flush(display);
        while (!frame_state.failed && !frame_state.ready) {
            if (wl_display_dispatch(display) < 0) {
                frame_state.failed = true;
            }
        }
        if (!frame_state.failed && frame_state.ready && output_rgba(frame_state, mapped)) {
            result = 0;
        }
    }

    if (mapped != MAP_FAILED) {
        munmap(mapped, static_cast<size_t>(frame_state.stride) * frame_state.height);
    }
    if (buffer) {
        wl_buffer_destroy(buffer);
    }
    if (fd >= 0) {
        close(fd);
    }
    hyprland_toplevel_export_frame_v1_destroy(frame);
    hyprland_toplevel_export_manager_v1_destroy(registry_state.manager);
    wl_registry_destroy(registry);
    wl_display_disconnect(display);
    return result;
}
