package vibedlc.ru.client.command.commands;

import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import net.minecraft.commands.SharedSuggestionProvider;
import vibedlc.ru.client.bot.BotManager;
import vibedlc.ru.api.utils.chat.ChatUtils;
import vibedlc.ru.client.command.AbstractCommand;
import vibedlc.ru.client.command.CommandHeader;

import java.util.List;

@CommandHeader(name = "bot", help = "Управление ботами")
public class BotCommand extends AbstractCommand {

    @Override
    public void build(LiteralArgumentBuilder<SharedSuggestionProvider> builder) {
        builder.executes(context -> {
            help();
            return SINGLE_SUCCESS;
        });

        builder.then(literal("connect")
                .then(argument("name", StringArgumentType.word())
                        .then(argument("address", StringArgumentType.word())
                                .executes(context -> {
                                    String name = context.getArgument("name", String.class);
                                    String address = context.getArgument("address", String.class);
                                    BotManager.connect(name, address);
                                    ChatUtils.send("Подключаю " + name + " к " + address);
                                    return SINGLE_SUCCESS;
                                }))));

        builder.then(literal("remove")
                .then(argument("name", StringArgumentType.word())
                        .suggests((context, suggestions) -> {
                            BotManager.getConnections().stream()
                                    .map(bot -> bot.name)
                                    .forEach(suggestions::suggest);
                            return suggestions.buildFuture();
                        })
                        .executes(context -> {
                            String name = context.getArgument("name", String.class);
                            ChatUtils.send(BotManager.remove(name) ? "Бот удалён" : "Бот не найден");
                            return SINGLE_SUCCESS;
                        })));

        builder.then(literal("control")
                .then(argument("name", StringArgumentType.word())
                        .suggests((context, suggestions) -> {
                            BotManager.getConnections().stream()
                                    .map(bot -> bot.name)
                                    .forEach(suggestions::suggest);
                            return suggestions.buildFuture();
                        })
                        .executes(context -> {
                            String name = context.getArgument("name", String.class);
                            ChatUtils.send(BotManager.control(name) ? "Управление переключено" : "Бот не найден");
                            return SINGLE_SUCCESS;
                        })));

        builder.then(literal("say")
                .then(argument("name", StringArgumentType.word())
                        .suggests((context, suggestions) -> {
                            BotManager.getConnections().stream()
                                    .map(bot -> bot.name)
                                    .forEach(suggestions::suggest);
                            return suggestions.buildFuture();
                        })
                        .then(argument("message", StringArgumentType.greedyString())
                                .executes(context -> {
                                    String name = context.getArgument("name", String.class);
                                    String message = context.getArgument("message", String.class);
                                    ChatUtils.send(BotManager.say(name, message) ? "Сообщение отправлено" : "Бот не найден");
                                    return SINGLE_SUCCESS;
                                }))));

        builder.then(literal("sayall")
                .then(argument("message", StringArgumentType.greedyString())
                        .executes(context -> {
                            String message = context.getArgument("message", String.class);
                            BotManager.sayAll(message);
                            ChatUtils.send("Сообщение отправлено всем ботам");
                            return SINGLE_SUCCESS;
                        })));

        builder.then(literal("return")
                .executes(context -> {
                    ChatUtils.send(BotManager.restore() ? "Сессия восстановлена" : "Нет сохранённой сессии");
                    return SINGLE_SUCCESS;
                }));

        builder.then(literal("list")
                .executes(context -> {
                    List<BotManager.BotConnection> bots = BotManager.getConnections();
                    ChatUtils.send(bots.isEmpty() ? "Список ботов пуст" : "Боты: " + bots.stream().map(bot -> bot.name).toList());
                    return SINGLE_SUCCESS;
                }));
    }

    private void help() {
        ChatUtils.send(".bot connect/remove/control/say/sayall/return/list");
    }
}
