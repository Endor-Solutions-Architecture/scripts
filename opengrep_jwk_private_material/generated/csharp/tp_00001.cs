using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"EC","kid":"_hcvBCE11JRU","alg":"ES256","crv":"P-256","x":"3nVhYcKqCBnKIgBTW1hJunB8kAUFko4CI_N8Z97Uuwl","y":"tQXy386p9InVJ2qdtqWjHPURAtMx5fxpzjRP7t1rK3E","d":"dqA85XKrz9Daz54qkUwFOSI9JbFuvGyr0jH2bWzCXwW8vd_6MZnIRQLgLyTQB-24"}
    var jwk = "{\"kty\":\"EC\",\"kid\":\"_hcvBCE11JRU\",\"alg\":\"ES256\",\"crv\":\"P-256\",\"x\":\"3nVhYcKqCBnKIgBTW1hJunB8kAUFko4CI_N8Z97Uuwl\",\"y\":\"tQXy386p9InVJ2qdtqWjHPURAtMx5fxpzjRP7t1rK3E\",\"d\":\"dqA85XKrz9Daz54qkUwFOSI9JbFuvGyr0jH2bWzCXwW8vd_6MZnIRQLgLyTQB-24\"}";
    var key = new JsonWebKey(jwk);
  }
}
