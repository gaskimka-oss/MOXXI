package vibedlc.ru.client.bot;

import io.netty.channel.Channel;
import io.netty.channel.ChannelDuplexHandler;
import io.netty.channel.ChannelHandlerContext;
import io.netty.util.ReferenceCountUtil;
import vibedlc.ru.client.mixin.MinecraftClientAccessor;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import net.minecraft.client.Minecraft;
import net.minecraft.client.User;
import net.minecraft.client.gui.Gui;
import net.minecraft.client.gui.components.BossHealthOverlay;
import net.minecraft.client.gui.components.LerpingBossEvent;
import net.minecraft.client.gui.screens.ConnectScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.multiplayer.JoinMultiplayerScreen;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.multiplayer.ClientPacketListener;
import net.minecraft.client.multiplayer.MultiPlayerGameMode;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.multiplayer.resolver.ServerAddress;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.Connection;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.common.ClientboundDisconnectPacket;
import net.minecraft.network.protocol.common.ClientboundKeepAlivePacket;
import net.minecraft.network.protocol.common.ClientboundPingPacket;
import net.minecraft.network.protocol.common.ServerboundKeepAlivePacket;
import net.minecraft.network.protocol.common.ServerboundPongPacket;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBossEventPacket;
import net.minecraft.network.protocol.game.ClientboundBundlePacket;
import net.minecraft.network.protocol.game.ClientboundRespawnPacket;
import net.minecraft.network.protocol.game.ClientboundSetActionBarTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket;
import net.minecraft.network.protocol.game.ClientboundSetTitlesAnimationPacket;
import net.minecraft.network.protocol.game.ClientboundSystemChatPacket;
import net.minecraft.network.protocol.game.ServerboundClientCommandPacket;
import net.minecraft.network.protocol.game.ServerboundContainerClosePacket;
import net.minecraft.network.protocol.game.ServerboundSwingPacket;
import net.minecraft.network.protocol.game.ServerboundUseItemPacket;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.Entity;

public final class BotManager {
    private static final List<BotConnection> connections = new CopyOnWriteArrayList<>();

    private static Field guiBossOverlayField;
    private static Field bossBarsField;

    private static Field cphWorldField;
    private static Field cphPlayerField;
    private static Field cphIMField;

    private static Field mcNetworkHandlerField;
    private static Field mcWorldField;
    private static Field mcPlayerField;
    private static Field mcCameraEntityField;
    private static Field mcInteractionMgrField;

    static {
        try {
            for (Field field : Gui.class.getDeclaredFields()) {
                if (BossHealthOverlay.class.isAssignableFrom(field.getType())) {
                    field.setAccessible(true);
                    guiBossOverlayField = field;
                    break;
                }
            }
        } catch (Throwable ignored) {
        }

        try {
            for (Field field : BossHealthOverlay.class.getDeclaredFields()) {
                if (Map.class.isAssignableFrom(field.getType())) {
                    field.setAccessible(true);
                    bossBarsField = field;
                    break;
                }
            }
        } catch (Throwable ignored) {
        }

        try {
            for (Field field : ClientPacketListener.class.getDeclaredFields()) {
                field.setAccessible(true);
                Class<?> type = field.getType();
                if (type == ClientLevel.class) {
                    cphWorldField = field;
                } else if (type == LocalPlayer.class) {
                    cphPlayerField = field;
                } else if (type == MultiPlayerGameMode.class) {
                    cphIMField = field;
                }
            }
        } catch (Throwable e) {
            System.err.println("[BotManager] Failed to find ClientPacketListener fields: " + e);
        }

        try {
            for (Field field : Minecraft.class.getDeclaredFields()) {
                field.setAccessible(true);
                Class<?> type = field.getType();
                if (type == ClientPacketListener.class) {
                    mcNetworkHandlerField = field;
                } else if (type == ClientLevel.class) {
                    mcWorldField = field;
                } else if (type == LocalPlayer.class) {
                    mcPlayerField = field;
                } else if (type == Entity.class) {
                    mcCameraEntityField = field;
                } else if (type == MultiPlayerGameMode.class) {
                    mcInteractionMgrField = field;
                }
            }
        } catch (Throwable e) {
            System.err.println("[BotManager] Failed to find Minecraft fields: " + e);
        }
    }

    private BotManager() {
    }

    private static void setMc(Field field, Object value) {
        try {
            if (field != null) {
                field.set(Minecraft.getInstance(), value);
            }
        } catch (Throwable ignored) {
        }
    }

    private static BossHealthOverlay getBossOverlay(Minecraft mc) {
        try {
            if (mc.gui == null || guiBossOverlayField == null) {
                return null;
            }
            return (BossHealthOverlay) guiBossOverlayField.get(mc.gui);
        } catch (Throwable ignored) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    private static <T> T fromCph(Field field, ClientPacketListener handler) {
        try {
            if (field == null || handler == null) {
                return null;
            }
            return (T) field.get(handler);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static void refreshBotCache(BotConnection bot) {
        if (bot == null || bot.handler == null) {
            return;
        }

        ClientLevel world = fromCph(cphWorldField, bot.handler);
        LocalPlayer player = fromCph(cphPlayerField, bot.handler);
        MultiPlayerGameMode gameMode = fromCph(cphIMField, bot.handler);

        if (world != null) {
            bot.world = world;
        }
        if (player != null) {
            bot.player = player;
        }
        if (gameMode != null) {
            bot.interactionManager = gameMode;
        }
    }

    public static List<BotConnection> getConnections() {
        return new ArrayList<>(connections);
    }

    public static boolean isFrozenConnection(Connection connection) {
        if (connection == null) {
            return false;
        }
        return connections.stream().anyMatch(bot -> bot.connection == connection);
    }

    public static void connect(String name, String address) {
        Minecraft mc = Minecraft.getInstance();

        if (name == null || name.isBlank()) {
            return;
        }

        if (address == null || address.isBlank()) {
            return;
        }

        if (mc.player == null || mc.level == null || mc.getConnection() == null) {
            return;
        }

        connections.removeIf(b -> b.name.equalsIgnoreCase(name));

        mc.execute(() -> {
            User session = createSessionWithName(mc.getUser(), name);

            freezeCurrentSession();

            setUserSession(mc, session);

            ConnectScreen.startConnecting(
                    new JoinMultiplayerScreen(new TitleScreen()),
                    mc,
                    ServerAddress.parseString(address),
                    new ServerData(address, address, ServerData.Type.OTHER),
                    false,
                    null
            );
        });
    }

    public static void pulseBots(boolean rightClick) {
        for (BotConnection bot : connections) {
            if (bot.handler == null || bot.player == null) {
                continue;
            }

            try {
                if (rightClick) {
                    bot.handler.send(new ServerboundUseItemPacket(
                            InteractionHand.MAIN_HAND,
                            0,
                            bot.player.getYRot(),
                            bot.player.getXRot()
                    ));
                } else {
                    bot.handler.send(new ServerboundSwingPacket(InteractionHand.MAIN_HAND));
                }
            } catch (Throwable ignored) {
            }
        }
    }

    public static void sayAll(String message) {
        if (message == null) {
            return;
        }

        for (BotConnection bot : connections) {
            if (bot.handler == null) {
                continue;
            }

            try {
                bot.handler.sendChat(message);
            } catch (Throwable ignored) {
            }
        }
    }

    public static boolean control(String name) {
        Minecraft mc = Minecraft.getInstance();

        if (name == null || name.isBlank()) {
            return false;
        }

        return connections.stream()
                .filter(b -> b.name.equalsIgnoreCase(name))
                .findFirst()
                .map(bot -> {
                    if (mc.getConnection() != null && mc.level != null && mc.player != null) {
                        freezeCurrentSession();
                    }

                    connections.remove(bot);

                    Channel ch = getChannel(bot.connection);
                    if (ch != null && ch.pipeline().get("bot_filter") != null) {
                        try {
                            ch.pipeline().remove("bot_filter");
                        } catch (Throwable ignored) {
                        }
                    }

                    refreshBotCache(bot);

                    setMc(mcNetworkHandlerField, bot.handler);
                    setMc(mcWorldField, bot.world);
                    setMc(mcPlayerField, bot.player);
                    setMc(mcInteractionMgrField, bot.interactionManager);
                    setMc(mcCameraEntityField, bot.player);

                    restoreBossBarsToClient(bot);

                    if (bot.world != null) {
                        try {
                            mc.setLevel(bot.world);
                        } catch (Throwable ignored) {
                        }
                    }

                    setMc(mcNetworkHandlerField, bot.handler);
                    setMc(mcWorldField, bot.world);
                    setMc(mcPlayerField, bot.player);
                    setMc(mcInteractionMgrField, bot.interactionManager);

                    if (bot.player != null) {
                        try {
                            mc.setCameraEntity(bot.player);
                        } catch (Throwable ignored) {
                        }
                    }

                    setUserSession(mc, createSessionWithName(mc.getUser(), bot.name));

                    setClientOverlayMessage(mc, bot.lastActionBar);

                    mc.gui.setScreen(null);

                    return true;
                })
                .orElse(false);
    }

    private static void freezeCurrentSession() {
        Minecraft mc = Minecraft.getInstance();

        if (mc.getConnection() == null || mc.level == null || mc.player == null) {
            return;
        }

        ClientPacketListener h = mc.getConnection();
        String name = mc.getUser().getName();

        connections.removeIf(b -> b.name.equalsIgnoreCase(name));

        BotConnection bot = new BotConnection(
                name,
                mc.getCurrentServer() != null ? mc.getCurrentServer().ip : "",
                h.getConnection(),
                h,
                mc.level,
                mc.player,
                mc.gameMode
        );

        saveBossBarsFromClient(bot);

        connections.add(bot);

        makeNettyBot(h, bot.name);

        setMc(mcNetworkHandlerField, null);
        setMc(mcWorldField, null);
        setMc(mcPlayerField, null);
        setMc(mcInteractionMgrField, null);
        setMc(mcCameraEntityField, null);

        setLevelRendererWorld(mc, null);

        setClientOverlayMessage(mc, Component.empty());
    }

    private static void makeNettyBot(ClientPacketListener handler, String name) {
        if (handler == null || handler.getConnection() == null) {
            return;
        }

        Channel channel = getChannel(handler.getConnection());

        if (channel == null) {
            return;
        }

        if (channel.pipeline().get("bot_filter") != null) {
            try {
                channel.pipeline().remove("bot_filter");
            } catch (Throwable ignored) {
            }
        }

        channel.pipeline().addBefore("packet_handler", "bot_filter", new ChannelDuplexHandler() {
            @Override
            @SuppressWarnings("unchecked")
            public void channelRead(ChannelHandlerContext ctx, Object msg) throws Exception {
                BotConnection bot = connections.stream()
                        .filter(b -> b.name.equalsIgnoreCase(name))
                        .findFirst()
                        .orElse(null);

                if (bot == null) {
                    super.channelRead(ctx, msg);
                    return;
                }

                if (msg instanceof Packet<?> packet && isConfigPacket(packet)) {
                    ReferenceCountUtil.release(msg);
                    return;
                }

                if (msg instanceof ClientboundBundlePacket bundle) {
                    try {
                        for (Packet<? super ClientGamePacketListener> packet : bundle.subPackets()) {
                            if (isConfigPacket(packet)) {
                                continue;
                            }
                            handleBotPacket(packet, bot, ctx);
                        }
                    } finally {
                        ReferenceCountUtil.release(msg);
                    }
                    return;
                }

                if (msg instanceof Packet<?> packet) {
                    boolean handled = handleBotPacket(
                            (Packet<? super ClientGamePacketListener>) packet,
                            bot,
                            ctx
                    );

                    if (handled) {
                        ReferenceCountUtil.release(msg);
                        return;
                    }
                }

                super.channelRead(ctx, msg);
            }
        });
    }

    private static boolean handleBotPacket(Packet<? super ClientGamePacketListener> p,
                                           BotConnection bot,
                                           ChannelHandlerContext ctx) {
        Minecraft mc = Minecraft.getInstance();

        if (p == null || bot == null || bot.handler == null) {
            return true;
        }

        if (p instanceof ClientboundKeepAlivePacket pk) {
            try {
                bot.handler.getConnection().send(new ServerboundKeepAlivePacket(pk.getId()));
            } catch (Throwable ignored) {
            }
            return true;
        }

        if (p instanceof ClientboundPingPacket pk) {
            try {
                bot.handler.getConnection().send(new ServerboundPongPacket(pk.getId()));
            } catch (Throwable ignored) {
            }
            return true;
        }

        if (p instanceof ClientboundDisconnectPacket) {
            connections.remove(bot);
            try {
                ctx.close();
            } catch (Throwable ignored) {
            }
            return true;
        }

        if (p instanceof ClientboundBossEventPacket pk && bossBarsField != null) {
            mc.execute(() -> applyBossBarPacketToBot(pk, bot));
            return true;
        }

        if (p instanceof ClientboundSetActionBarTextPacket pk) {
            bot.lastActionBar = pk.text();
            return true;
        }

        if (p instanceof ClientboundSystemChatPacket pk && pk.overlay()) {
            bot.lastActionBar = pk.content();
            return true;
        }

        if (p instanceof ClientboundSetTitleTextPacket || p instanceof ClientboundSetSubtitleTextPacket || p instanceof ClientboundSetTitlesAnimationPacket) {
            return true;
        }

        if (isPlayPacket(p)) {
            mc.execute(() -> applyPacketToBot(p, bot));
            return true;
        }

        if (isConfigPacket(p)) {
            return true;
        }

        mc.execute(() -> {
            try {
                p.handle(bot.handler);
            } catch (Throwable t) {
                System.err.println("[BotManager] Failed to apply bot packet: " + p.getClass().getName());
            }
        });

        return true;
    }

    private static boolean isConfigPacket(Packet<?> packet) {
        if (packet == null) {
            return false;
        }
        Package pkg = packet.getClass().getPackage();
        return pkg != null && pkg.getName().contains(".protocol.configuration");
    }

    private static boolean isPlayPacket(Packet<?> packet) {
        if (packet == null) {
            return false;
        }
        Package pkg = packet.getClass().getPackage();
        return pkg != null && pkg.getName().contains(".protocol.game");
    }

    private static void applyPacketToBot(Packet<? super ClientGamePacketListener> packet,
                                         BotConnection bot) {
        Minecraft mc = Minecraft.getInstance();

        ClientPacketListener oldHandler = mc.getConnection();
        ClientLevel oldWorld = mc.level;
        LocalPlayer oldPlayer = mc.player;
        MultiPlayerGameMode oldInteractionManager = mc.gameMode;
        Entity oldCameraEntity = mc.getCameraEntity();
        Screen oldScreen = mc.gui.screen();

        boolean mutatesClientState = packet instanceof ClientboundRespawnPacket;

        try {
            refreshBotCache(bot);

            setMc(mcNetworkHandlerField, bot.handler);
            setMc(mcWorldField, bot.world);
            setMc(mcPlayerField, bot.player);
            setMc(mcInteractionMgrField, bot.interactionManager);

            if (bot.player != null) {
                setMc(mcCameraEntityField, bot.player);
            }

            packet.handle(bot.handler);

            refreshBotCache(bot);

            if (cphWorldField == null && mc.level != null) {
                bot.world = mc.level;
            }
            if (cphPlayerField == null && mc.player != null) {
                bot.player = mc.player;
            }

            if (bot.player != null && bot.player.getHealth() <= 0.0F && bot.handler != null) {
                try {
                    bot.handler.send(new ServerboundClientCommandPacket(ServerboundClientCommandPacket.Action.PERFORM_RESPAWN));
                } catch (Throwable ignored) {
                }
            }
        } catch (Throwable t) {
            System.err.println("[BotManager] Failed to apply bot packet: " + packet.getClass().getName());
        } finally {
            setMc(mcNetworkHandlerField, oldHandler);
            setMc(mcWorldField, oldWorld);
            setMc(mcPlayerField, oldPlayer);
            setMc(mcInteractionMgrField, oldInteractionManager);
            setMc(mcCameraEntityField, oldCameraEntity);

            if (mutatesClientState && oldWorld != null) {
                setLevelRendererWorld(mc, oldWorld);
            }

            try {
                if (oldCameraEntity != null) {
                    mc.setCameraEntity(oldCameraEntity);
                }
            } catch (Throwable ignored) {
            }

            if (mc.gui.screen() != oldScreen) {
                try {
                    mc.gui.setScreen(oldScreen);
                } catch (Throwable ignored) {
                }
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static void applyBossBarPacketToBot(ClientboundBossEventPacket packet, BotConnection bot) {
        Minecraft mc = Minecraft.getInstance();
        try {
            BossHealthOverlay overlay = getBossOverlay(mc);
            if (overlay == null || bossBarsField == null) {
                return;
            }

            Map<UUID, LerpingBossEvent> originalBars =
                    (Map<UUID, LerpingBossEvent>) bossBarsField.get(overlay);

            bossBarsField.set(overlay, bot.bossBars);

            try {
                overlay.update(packet);
            } finally {
                bossBarsField.set(overlay, originalBars);
            }
        } catch (Throwable ignored) {
        }
    }

    @SuppressWarnings("unchecked")
    private static void saveBossBarsFromClient(BotConnection bot) {
        Minecraft mc = Minecraft.getInstance();
        try {
            BossHealthOverlay overlay = getBossOverlay(mc);
            if (bossBarsField == null || overlay == null) {
                return;
            }

            Map<UUID, LerpingBossEvent> hudMap =
                    (Map<UUID, LerpingBossEvent>) bossBarsField.get(overlay);

            bot.bossBars.clear();
            bot.bossBars.putAll(hudMap);
            hudMap.clear();
        } catch (Throwable ignored) {
        }
    }

    @SuppressWarnings("unchecked")
    private static void restoreBossBarsToClient(BotConnection bot) {
        Minecraft mc = Minecraft.getInstance();
        try {
            BossHealthOverlay overlay = getBossOverlay(mc);
            if (bossBarsField == null || overlay == null) {
                return;
            }

            Map<UUID, LerpingBossEvent> hudMap =
                    (Map<UUID, LerpingBossEvent>) bossBarsField.get(overlay);

            hudMap.clear();
            hudMap.putAll(bot.bossBars);
        } catch (Throwable ignored) {
        }
    }

    public static boolean say(String name, String message) {
        if (name == null || message == null) {
            return false;
        }

        return connections.stream()
                .filter(b -> b.name.equalsIgnoreCase(name))
                .findFirst()
                .map(bot -> {
                    try {
                        bot.handler.sendChat(message);
                    } catch (Throwable ignored) {
                    }
                    return true;
                })
                .orElse(false);
    }

    public static boolean closeScreen(String name) {
        if (name == null) {
            return false;
        }

        return connections.stream()
                .filter(bot -> bot.name.equalsIgnoreCase(name))
                .findFirst()
                .map(bot -> {
                    if (bot.handler == null || bot.player == null || bot.player.containerMenu == null) {
                        return false;
                    }
                    try {
                        bot.handler.send(new ServerboundContainerClosePacket(bot.player.containerMenu.containerId));
                        return true;
                    } catch (Throwable ignored) {
                        return false;
                    }
                })
                .orElse(false);
    }

    public static boolean remove(String name) {
        if (name == null) {
            return false;
        }

        return connections.removeIf(bot -> {
            if (!bot.name.equalsIgnoreCase(name)) {
                return false;
            }

            try {
                bot.connection.disconnect(Component.literal("Bot Removed"));
            } catch (Throwable ignored) {
            }

            Channel ch = getChannel(bot.connection);

            if (ch != null && ch.pipeline().get("bot_filter") != null) {
                try {
                    ch.pipeline().remove("bot_filter");
                } catch (Throwable ignored) {
                }
            }

            return true;
        });
    }

    public static boolean restore() {
        if (connections.isEmpty()) {
            return false;
        }

        return control(connections.get(connections.size() - 1).name);
    }

    private static Channel getChannel(Connection c) {
        if (c == null) {
            return null;
        }

        try {
            for (Field f : Connection.class.getDeclaredFields()) {
                if (Channel.class.isAssignableFrom(f.getType())) {
                    f.setAccessible(true);
                    return (Channel) f.get(c);
                }
            }
        } catch (Throwable ignored) {
        }

        return null;
    }

    private static void setLevelRendererWorld(Minecraft mc, ClientLevel level) {
        if (mc == null) {
            return;
        }

        try {
            mc.setLevel(level);
        } catch (Throwable ignored) {
        }
    }

    private static void setClientOverlayMessage(Minecraft mc, Component text) {
        if (mc == null || mc.gui == null) return;
        try {
            for (Method m : mc.gui.getClass().getMethods()) {
                Class<?>[] params = m.getParameterTypes();
                if (params.length == 2 && Component.class.isAssignableFrom(params[0]) && params[1] == boolean.class) {
                    m.invoke(mc.gui, text != null ? text : Component.empty(), false);
                    return;
                } else if (params.length == 1 && Component.class.isAssignableFrom(params[0])) {
                    m.invoke(mc.gui, text != null ? text : Component.empty());
                    return;
                }
            }
        } catch (Throwable ignored) {
        }
    }

    private static void setUserSession(Minecraft mc, User user) {
        try {
            ((MinecraftClientAccessor) mc).setSession(user);
        } catch (Throwable t) {
            try {
                for (Field field : Minecraft.class.getDeclaredFields()) {
                    if (field.getType() == User.class) {
                        field.setAccessible(true);
                        field.set(mc, user);
                        return;
                    }
                }
            } catch (Throwable ignored) {
            }
        }
    }

    private static User createSessionWithName(User current, String name) {
        String token = (current != null && current.getAccessToken() != null) ? current.getAccessToken() : "";
        UUID uuid = UUID.nameUUIDFromBytes(("OfflinePlayer:" + name).getBytes(StandardCharsets.UTF_8));

        try {
            return new User(
                    name,
                    uuid,
                    token,
                    Optional.empty(),
                    Optional.empty()
            );
        } catch (Throwable ignored) {
        }

        try {
            for (Constructor<?> constructor : User.class.getDeclaredConstructors()) {
                constructor.setAccessible(true);
                Class<?>[] pts = constructor.getParameterTypes();
                if (pts.length == 5 && pts[0] == String.class && pts[1] == UUID.class) {
                    return (User) constructor.newInstance(
                            name,
                            uuid,
                            token,
                            Optional.empty(),
                            Optional.empty()
                    );
                } else if (pts.length == 6 && pts[0] == String.class && pts[1] == UUID.class) {
                    Object typeVal = null;
                    if (pts[5].isEnum()) {
                        Object[] constants = pts[5].getEnumConstants();
                        if (constants != null && constants.length > 0) {
                            typeVal = constants[0];
                        }
                    }
                    return (User) constructor.newInstance(
                            name,
                            uuid,
                            token,
                            Optional.empty(),
                            Optional.empty(),
                            typeVal
                    );
                } else if (pts.length == 4 && pts[0] == String.class && pts[1] == UUID.class) {
                    return (User) constructor.newInstance(
                            name,
                            uuid,
                            token,
                            Optional.empty()
                    );
                }
            }
        } catch (Throwable e) {
            throw new RuntimeException("Failed to create bot session", e);
        }
        throw new RuntimeException("No matching User constructor found");
    }

    public static class BotConnection {
        public final String name;
        public final String address;
        public final Connection connection;
        public final ClientPacketListener handler;

        public ClientLevel world;
        public LocalPlayer player;
        public MultiPlayerGameMode interactionManager;

        public final Map<UUID, LerpingBossEvent> bossBars = new HashMap<>();
        public Component lastActionBar;

        public BotConnection(String name,
                             String address,
                             Connection connection,
                             ClientPacketListener handler,
                             ClientLevel world,
                             LocalPlayer player,
                             MultiPlayerGameMode interactionManager) {
            this.name = name;
            this.address = address;
            this.connection = connection;
            this.handler = handler;
            this.world = world;
            this.player = player;
            this.interactionManager = interactionManager;
        }

        public String name() { return name; }
        public String address() { return address; }
        public Connection connection() { return connection; }
        public ClientPacketListener handler() { return handler; }
        public ClientLevel world() { return world; }
        public LocalPlayer player() { return player; }
        public MultiPlayerGameMode interactionManager() { return interactionManager; }
        public Map<UUID, LerpingBossEvent> bossBars() { return bossBars; }
        public Component lastActionBar() { return lastActionBar; }
    }
}
