package ai.juno.app.ui

import androidx.compose.runtime.Composable
import ai.juno.app.MainViewModel
import ai.juno.app.ui.chat.ChatSheetContent

@Composable
fun ChatSheet(viewModel: MainViewModel) {
  ChatSheetContent(viewModel = viewModel)
}
