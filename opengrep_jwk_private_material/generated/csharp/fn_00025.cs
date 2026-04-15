using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"pkRnhn7rbzSU","alg":"RS256","n":"sjryKNmxiv8ASKTSnmUTBhMCW5PocUx7qS8YI5x_Rre9QOZa","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"pkRnhn7rbzSU\",\"alg\":\"RS256\",\"n\":\"sjryKNmxiv8ASKTSnmUTBhMCW5PocUx7qS8YI5x_Rre9QOZa\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
